import os

import boto3

import file_table
from config import load_config
from detect import detect_tags, merge_max
from events import uploaded_objects
from frames import extract_frames

VIDEO_EXTENSIONS = {".mp4", ".mov"}

s3 = boto3.client("s3")


def tag_image(bucket, key, config):
    image = {"S3Object": {"Bucket": bucket, "Name": key}}
    return detect_tags(image, config)


def tag_video(bucket, key, config):
    local_path = f"/tmp/{os.path.basename(key)}"
    s3.download_file(bucket, key, local_path)
    try:
        per_frame = (
            detect_tags({"Bytes": frame}, config)
            for frame in extract_frames(local_path)
        )
        return merge_max(per_frame)
    finally:
        os.remove(local_path)


def handler(event, context):
    config = load_config()
    for bucket, key in uploaded_objects(event):
        file_id, ext = os.path.splitext(os.path.basename(key))

        try:
            if ext.lower() in VIDEO_EXTENSIONS:
                tags = tag_video(bucket, key, config)
            else:
                tags = tag_image(bucket, key, config)
        except Exception:
            file_table.mark_failed(file_id)
            raise

        file_table.save_tags(file_id, tags)
