import cv2
import numpy as np


def make_thumbnail(image_bytes, max_side=256, quality=80):
    """Shrink so the longer side is at most max_side, keep aspect ratio, return JPEG bytes."""
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("cannot decode image")

    height, width = image.shape[:2]
    scale = min(1.0, max_side / max(height, width))
    if scale < 1.0:
        size = (round(width * scale), round(height * scale))
        image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)

    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("cannot encode thumbnail")
    return encoded.tobytes()
