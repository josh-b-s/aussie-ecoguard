import os

from config import load_config
from detect import detect_tags

BUCKET = os.environ["BUCKET"]
QUERY_PREFIX = "search-temp/"


def handler(event, context):
    """Detect tags for a temporary query image. Input: {"key": "search-temp/<id>.jpg"}."""
    key = event["key"]
    if not key.startswith(QUERY_PREFIX):
        raise ValueError(f"key must start with {QUERY_PREFIX}")
    image = {"S3Object": {"Bucket": BUCKET, "Name": key}}
    return {"tags": detect_tags(image, load_config())}
