"""POST /match: rank candidate images by similarity to a lost-pet photo.

The AWS search Lambda sends presigned S3 URLs; this service never touches S3
credentials. Identity comes from the user's Cognito ID token, forwarded as a
Bearer token. Visibility (own or public files only) is decided by the AWS side
when it picks the candidates and signs their URLs.
"""

import logging
import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import features
from auth import get_current_user
from urlcheck import UrlRejected, check_candidate, check_url

log = logging.getLogger("match")
router = APIRouter()

MAX_CANDIDATES = 20
MAX_BYTES = 10 * 1024 * 1024
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "10"))
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.25"))
WORKERS = 6


class FetchError(RuntimeError):
    """The image could not be downloaded."""


class Candidate(BaseModel):
    file_id: str = Field(max_length=64)
    url: str = Field(max_length=2048)


class MatchRequest(BaseModel):
    query_url: str = Field(max_length=2048)
    candidates: list[Candidate] = Field(default_factory=list, max_length=MAX_CANDIDATES)


def fetch_image(url: str) -> bytes:
    """Download an already validated URL. Never follows redirects."""
    try:
        with requests.get(
            url, timeout=(3, 10), stream=True, allow_redirects=False
        ) as resp:
            if resp.status_code != 200:
                raise FetchError(f"status {resp.status_code}")
            if int(resp.headers.get("Content-Length") or 0) > MAX_BYTES:
                raise FetchError("image too large")
            buf = bytearray()
            for chunk in resp.iter_content(65536):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise FetchError("image too large")
            return bytes(buf)
    except (requests.RequestException, ValueError) as exc:
        raise FetchError("download failed") from exc


# Candidate features are cached per S3 object path. Objects are named after the
# SHA-256 of their content, so a path always maps to the same image and the
# cache cannot be poisoned by what a caller claims in the request body.
_CACHE_MAX = 500
_cache: "OrderedDict[str, features.Features]" = OrderedDict()
_lock = threading.Lock()


def _cache_get(key: str):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key: str, value: features.Features) -> None:
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def _candidate_features(path: str, url: str):
    """Features for one candidate, or None if it cannot be downloaded/decoded."""
    cached = _cache_get(path)
    if cached is not None:
        return cached
    try:
        data = fetch_image(url)
        feats = features.analyze(data)
    except (FetchError, features.ImageError):
        return None
    _cache_put(path, feats)
    return feats


@router.post("/match")
def match(req: MatchRequest, user: dict = Depends(get_current_user)) -> dict:
    try:
        check_url(req.query_url, ("/search-temp/",))
        checked = [(c.file_id, check_candidate(c.file_id, c.url), c.url) for c in req.candidates]
    except UrlRejected as exc:
        raise HTTPException(status_code=400, detail=f"Rejected URL: {exc}")
    if len({file_id for file_id, _, _ in checked}) != len(checked):
        raise HTTPException(status_code=400, detail="Duplicate file_id in candidates")

    try:
        query = features.analyze(fetch_image(req.query_url))
    except (FetchError, features.ImageError):
        raise HTTPException(status_code=400, detail="Could not read the query image")
    except features.VisionError:
        log.exception("Vision failed on the query image")
        raise HTTPException(status_code=502, detail="Image analysis failed")

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            analysed = list(pool.map(lambda c: _candidate_features(c[1], c[2]), checked))
    except features.VisionError:
        log.exception("Vision failed on a candidate image")
        raise HTTPException(status_code=502, detail="Image analysis failed")

    scored, skipped = [], 0
    for (file_id, _, _), feats in zip(checked, analysed):
        if feats is None:
            skipped += 1
            continue
        value = features.score(query, feats)
        if value >= MIN_SCORE:
            scored.append({"file_id": file_id, "score": value})
    scored.sort(key=lambda m: (-m["score"], m["file_id"]))

    log.info("match: %d candidates, %d skipped, %d returned", len(checked), skipped, len(scored[:MAX_RESULTS]))
    return {"matches": scored[:MAX_RESULTS], "skipped": skipped}
