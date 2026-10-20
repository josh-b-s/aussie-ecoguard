"""Offline tests for /match: no network, no Cloud Vision, no real tokens."""

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["COGNITO_REGION"] = "ap-southeast-2"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-2_TESTPOOL"
os.environ["COGNITO_APP_CLIENT_ID"] = "testclient123"

import features  # noqa: E402
import match  # noqa: E402
from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402
from urlcheck import UrlRejected, check_candidate, check_url  # noqa: E402

HOST = "ecoguard-media-853611856490.s3.ap-southeast-2.amazonaws.com"
ID_A = "a" * 64
ID_B = "b" * 64
ID_C = "c" * 64


def jpeg(color):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "JPEG")
    return buf.getvalue()


BROWN = jpeg((139, 90, 43))
BROWN2 = jpeg((135, 85, 40))
BLUE = jpeg((20, 40, 200))

# Stand-in for Cloud Vision, keyed by image bytes.
LABELS = {
    BROWN: {"dog": 0.95, "fur": 0.9},
    BROWN2: {"dog": 0.9, "fur": 0.85},
    BLUE: {"sky": 0.9, "blue": 0.8},
}
IMAGES = {}  # path -> bytes served by the fake downloader
vision_calls = []


def url(prefix, name):
    return f"https://{HOST}/{prefix}/{name}?X-Amz-Signature=abc"


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"sub": "user-1"}
    match._cache.clear()
    vision_calls.clear()
    IMAGES.clear()

    def fake_fetch(u):
        path = u.split(HOST)[1].split("?")[0]
        if path not in IMAGES:
            raise match.FetchError("missing")
        return IMAGES[path]

    def fake_labels(data):
        vision_calls.append(data)
        return LABELS[data]

    monkeypatch.setattr(match, "fetch_image", fake_fetch)
    monkeypatch.setattr(features, "vision_labels", fake_labels)
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def body(candidates):
    return {"query_url": url("search-temp", "q.jpg"), "candidates": candidates}


def cand(file_id, prefix="thumbnails"):
    return {"file_id": file_id, "url": url(prefix, f"{file_id}.jpg")}


def serve(file_id, data, prefix="thumbnails"):
    IMAGES[f"/{prefix}/{file_id}.jpg"] = data


# ---------- ranking ----------

def test_similar_image_ranks_first_and_dissimilar_is_dropped():
    IMAGES["/search-temp/q.jpg"] = BROWN
    serve(ID_A, BLUE)
    serve(ID_B, BROWN2)
    r = client.post("/match", json=body([cand(ID_A), cand(ID_B)]))
    assert r.status_code == 200
    matches = r.json()["matches"]
    assert [m["file_id"] for m in matches] == [ID_B]
    assert 0.8 < matches[0]["score"] <= 1.0


def test_results_sorted_best_first():
    IMAGES["/search-temp/q.jpg"] = BROWN
    serve(ID_A, BROWN2)
    serve(ID_B, BROWN)
    matches = client.post("/match", json=body([cand(ID_A), cand(ID_B)])).json()["matches"]
    assert [m["file_id"] for m in matches] == [ID_B, ID_A]
    assert matches[0]["score"] >= matches[1]["score"]


def test_empty_candidates_returns_empty_list():
    IMAGES["/search-temp/q.jpg"] = BROWN
    r = client.post("/match", json=body([]))
    assert r.status_code == 200
    assert r.json() == {"matches": [], "skipped": 0}


def test_unreachable_candidate_is_skipped_not_fatal():
    IMAGES["/search-temp/q.jpg"] = BROWN
    serve(ID_B, BROWN2)  # ID_A is not served, so its download fails
    r = client.post("/match", json=body([cand(ID_A), cand(ID_B)]))
    assert r.status_code == 200
    assert r.json()["skipped"] == 1
    assert [m["file_id"] for m in r.json()["matches"]] == [ID_B]


def test_candidate_features_are_cached_between_requests():
    IMAGES["/search-temp/q.jpg"] = BROWN
    serve(ID_B, BROWN2)
    client.post("/match", json=body([cand(ID_B)]))
    first = len(vision_calls)  # query + one candidate
    client.post("/match", json=body([cand(ID_B)]))
    assert len(vision_calls) == first + 1  # only the new query is analysed


# ---------- errors ----------

def test_vision_failure_returns_502(monkeypatch):
    IMAGES["/search-temp/q.jpg"] = BROWN

    def boom(_):
        raise features.VisionError("down")

    monkeypatch.setattr(features, "vision_labels", boom)
    assert client.post("/match", json=body([])).status_code == 502


def test_unreadable_query_image_returns_400():
    r = client.post("/match", json=body([]))  # query not served
    assert r.status_code == 400


def test_non_image_bytes_are_rejected_before_vision():
    IMAGES["/search-temp/q.jpg"] = b"<html>not an image</html>"
    assert client.post("/match", json=body([])).status_code == 400
    assert vision_calls == []


def test_too_many_candidates_returns_400():
    IMAGES["/search-temp/q.jpg"] = BROWN
    many = [cand(f"{i:064x}") for i in range(match.MAX_CANDIDATES + 1)]
    assert client.post("/match", json=body(many)).status_code == 400


def test_duplicate_file_ids_return_400():
    IMAGES["/search-temp/q.jpg"] = BROWN
    assert client.post("/match", json=body([cand(ID_A), cand(ID_A)])).status_code == 400


def test_malformed_body_returns_400():
    assert client.post("/match", json={"nope": 1}).status_code == 400


def test_foreign_host_is_rejected_and_never_fetched(monkeypatch):
    calls = []
    monkeypatch.setattr(match, "fetch_image", lambda u: calls.append(u))
    evil = {"query_url": "https://evil.example.com/search-temp/q.jpg", "candidates": []}
    assert client.post("/match", json=evil).status_code == 400
    assert calls == []


def test_requires_token():
    app.dependency_overrides.clear()
    assert client.post("/match", json=body([])).status_code == 401


# ---------- URL allowlist ----------

@pytest.mark.parametrize(
    "bad",
    [
        f"http://{HOST}/search-temp/q.jpg",  # not https
        "https://evil.example.com/search-temp/q.jpg",  # other host
        f"https://{HOST}.evil.com/search-temp/q.jpg",  # lookalike host
        f"https://user:pw@{HOST}/search-temp/q.jpg",  # credentials
        f"https://{HOST}:8443/search-temp/q.jpg",  # odd port
        f"https://{HOST}/uploads/q.jpg",  # wrong prefix for a query
        f"https://{HOST}/search-temp/../uploads/q.jpg",  # traversal
        f"https://{HOST}\\@evil.example.com/search-temp/q.jpg",  # parser trick
        f"https://{HOST}/search-temp/q.jpg x",  # whitespace
        "https://169.254.169.254/search-temp/q.jpg",  # metadata server
    ],
)
def test_query_url_rejections(bad):
    with pytest.raises(UrlRejected):
        check_url(bad, ("/search-temp/",))


def test_good_query_url_accepted():
    assert check_url(url("search-temp", "q.jpg"), ("/search-temp/",)) == "/search-temp/q.jpg"


def test_candidate_must_match_its_file_id():
    with pytest.raises(UrlRejected):
        check_candidate(ID_A, url("thumbnails", f"{ID_B}.jpg"))
    with pytest.raises(UrlRejected):
        check_candidate("not-a-hash", url("thumbnails", "not-a-hash.jpg"))
    with pytest.raises(UrlRejected):
        check_candidate(ID_A, url("search-temp", f"{ID_A}.jpg"))
    assert check_candidate(ID_A, url("thumbnails", f"{ID_A}.jpg")) == f"/thumbnails/{ID_A}.jpg"
    assert check_candidate(ID_C, url("uploads", f"{ID_C}.png")) == f"/uploads/{ID_C}.png"


def test_long_presigned_url_with_session_token_is_accepted():
    """Presigned URLs made with temporary credentials exceed 2,000 characters."""
    token = "A" * 2500
    long_query = url("search-temp", "q.jpg") + f"&X-Amz-Security-Token={token}"
    long_cand = url("thumbnails", f"{ID_B}.jpg") + f"&X-Amz-Security-Token={token}"
    IMAGES["/search-temp/q.jpg"] = BROWN
    serve(ID_B, BROWN2)
    r = client.post(
        "/match",
        json={"query_url": long_query, "candidates": [{"file_id": ID_B, "url": long_cand}]},
    )
    assert r.status_code == 200
    assert [m["file_id"] for m in r.json()["matches"]] == [ID_B]
