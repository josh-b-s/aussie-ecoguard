import boto3

rekognition = boto3.client("rekognition")


def detect_tags(image, config):
    """Return {tag: count} for one image.

    image is a Rekognition Image dict: {"Bytes": ...} or {"S3Object": {...}}.
    """
    result = rekognition.detect_labels(
        Image=image, MinConfidence=config["min_confidence"]
    )
    tags = {}
    for label in result["Labels"]:
        tag = config["label_map"].get(label["Name"])
        if tag is None:
            continue
        # A label can be detected without per-object boxes, so count it as one
        count = max(len(label["Instances"]), 1)
        tags[tag] = max(tags.get(tag, 0), count)
    return tags


def merge_max(per_frame_tags):
    """Combine frame results by taking the highest count seen per tag."""
    merged = {}
    for tags in per_frame_tags:
        for tag, count in tags.items():
            merged[tag] = max(merged.get(tag, 0), count)
    return merged
