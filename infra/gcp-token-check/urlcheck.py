"""Validation of URLs that /match is allowed to fetch.

The service downloads images from URLs sent by the client, which is an SSRF
risk if left open. Only our own S3 bucket host is allowed, over https, and the
path must sit under an expected prefix. Redirects are never followed (see
match.fetch_image), so a URL on the allowed host cannot bounce elsewhere.
"""

import os
import re
from urllib.parse import urlsplit

DEFAULT_HOST = "ecoguard-media-853611856490.s3.ap-southeast-2.amazonaws.com"
FILE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
# Backslashes, whitespace and control characters are where URL parsers disagree.
_BAD_CHARS = re.compile(r"[\\\s\x00-\x1f\x7f]")


class UrlRejected(ValueError):
    """The URL is not one we are willing to fetch."""


def allowed_hosts() -> set[str]:
    raw = os.environ.get("ALLOWED_S3_HOSTS", DEFAULT_HOST)
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def check_url(url: str, prefixes: tuple[str, ...]) -> str:
    """Return the object path of an allowed URL, or raise UrlRejected."""
    if _BAD_CHARS.search(url):
        raise UrlRejected("invalid characters in URL")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise UrlRejected("URL must use https")
    if parts.username is not None or parts.password is not None:
        raise UrlRejected("credentials in URL are not allowed")
    if parts.port not in (None, 443):
        raise UrlRejected("unexpected port")
    if (parts.hostname or "") not in allowed_hosts():
        raise UrlRejected("host is not allowed")
    path = parts.path
    if not any(path.startswith(p) for p in prefixes):
        raise UrlRejected("path is not allowed")
    if ".." in path.split("/") or "//" in path:
        raise UrlRejected("invalid path")
    return path


def check_candidate(file_id: str, url: str) -> str:
    """Candidate URLs must be the object named after their own file_id."""
    if not FILE_ID_RE.match(file_id):
        raise UrlRejected("file_id must be 64 lowercase hex characters")
    path = check_url(url, ("/thumbnails/", "/uploads/"))
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if stem != file_id:
        raise UrlRejected("URL does not belong to file_id")
    return path
