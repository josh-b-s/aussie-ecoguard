import json
import os
import re

import boto3

import file_table

BUCKET = os.environ["BUCKET"]
URL_TTL_SECONDS = 300

# contentType -> (extension, file_type stored in the table)
ALLOWED_TYPES = {
    "image/jpeg": ("jpg", "image"),
    "image/png": ("png", "image"),
    "video/mp4": ("mp4", "video"),
    "video/quicktime": ("mov", "video"),
}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

s3 = boto3.client("s3")


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    body = json.loads(event["body"] or "{}")
    content_type = body.get("contentType")
    sha256 = body.get("sha256", "")

    if content_type not in ALLOWED_TYPES or not SHA256_HEX.match(sha256):
        return respond(400, {"error": "unsupported contentType or invalid sha256"})

    ext, file_type = ALLOWED_TYPES[content_type]
    key = f"uploads/{sha256}.{ext}"
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]

    if not file_table.create_pending(sha256, file_type, key, user_id):
        return respond(200, {"duplicate": True, "fileId": sha256})

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=URL_TTL_SECONDS,
    )
    return respond(200, {"duplicate": False, "fileId": sha256, "uploadUrl": upload_url})
