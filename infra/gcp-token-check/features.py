"""Image features for lost-pet matching.

Two signals are combined:
  - Cloud Vision label detection (what the image shows: dog, fur, ...).
    This is the only paid call: 1 unit per image, first 1,000 units/month free.
  - A colour histogram computed locally with Pillow (free). Fur colour is the
    strongest cue for telling two animals of the same kind apart.
"""

import io
from typing import NamedTuple

from PIL import Image

Image.MAX_IMAGE_PIXELS = 50_000_000  # refuse decompression bombs

LABEL_LIMIT = 20
MIN_LABEL_SCORE = 0.6
BINS = 4  # per channel, so 64 colour bins
LABEL_WEIGHT = 0.6
COLOR_WEIGHT = 0.4

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ImageError(ValueError):
    """The bytes are not a usable JPEG or PNG."""


class VisionError(RuntimeError):
    """The Cloud Vision call failed."""


class Features(NamedTuple):
    labels: dict[str, float]
    hist: list[float]


def check_image_bytes(data: bytes) -> None:
    if not (data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC)):
        raise ImageError("only JPEG and PNG images are supported")


def color_histogram(data: bytes) -> list[float]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > Image.MAX_IMAGE_PIXELS:
                raise ImageError("image is too large")
            img.draft("RGB", (128, 128))
            small = img.convert("RGB").resize((32, 32))
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError("could not decode image") from exc

    step = 256 // BINS
    counts = [0] * (BINS**3)
    raw = small.tobytes()
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        counts[(r // step) * BINS * BINS + (g // step) * BINS + (b // step)] += 1
    total = sum(counts)
    return [c / total for c in counts]


_client = None


def vision_labels(data: bytes) -> dict[str, float]:
    """Label -> confidence for the image, using Application Default Credentials."""
    global _client
    try:
        from google.cloud import vision

        if _client is None:
            _client = vision.ImageAnnotatorClient()
        resp = _client.label_detection(
            image=vision.Image(content=data), max_results=LABEL_LIMIT, timeout=20
        )
    except Exception as exc:
        raise VisionError("vision request failed") from exc
    if resp.error.message:
        raise VisionError("vision returned an error")
    return {
        a.description.lower(): float(a.score)
        for a in resp.label_annotations
        if a.score >= MIN_LABEL_SCORE
    }


def analyze(data: bytes) -> Features:
    """Cheap local checks first, so bad input never costs a Vision call."""
    check_image_bytes(data)
    hist = color_histogram(data)
    return Features(labels=vision_labels(data), hist=hist)


def label_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Weighted Jaccard: 1.0 for identical label sets, 0.0 for disjoint ones."""
    keys = set(a) | set(b)
    union = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    if union == 0:
        return 0.0
    return sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys) / union


def color_similarity(h1: list[float], h2: list[float]) -> float:
    """Histogram intersection: 1.0 for identical colour distributions."""
    return sum(min(x, y) for x, y in zip(h1, h2))


def score(query: Features, candidate: Features) -> float:
    s = LABEL_WEIGHT * label_similarity(query.labels, candidate.labels)
    s += COLOR_WEIGHT * color_similarity(query.hist, candidate.hist)
    return round(s, 3)
