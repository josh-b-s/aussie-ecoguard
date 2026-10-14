import os

import boto3

import file_table
from events import uploaded_objects
from thumbnail import make_thumbnail

IMAGE_EXTENSIONS = {".jpg", ".png"}

s3 = boto3.client("s3")


def handler(event, context):
    for bucket, key in uploaded_objects(event):
        file_id, ext = os.path.splitext(os.path.basename(key))
        if ext.lower() not in IMAGE_EXTENSIONS:
            continue

        original = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        thumbnail_key = f"thumbnails/{file_id}.jpg"
        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=make_thumbnail(original),
            ContentType="image/jpeg",
        )
        file_table.set_thumbnail_key(file_id, thumbnail_key)
