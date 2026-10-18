
import json
import os
import logging
import time
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

table = dynamodb.Table(os.environ["TABLE"])
temp_table = dynamodb.Table(os.environ["TEMP_TABLE"])
BUCKET = os.environ["BUCKET"]

DETECT_FUNCTION = os.environ.get(
    "DETECT_FUNCTION",
    "ecoguard-detect"
)

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173"
)


def json_converter(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    raise TypeError(
        f"Cannot serialize {type(value).__name__}"
    )


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin"
        },
        "body": json.dumps(body, default=json_converter)
    }


def detect_tags(image_key):
    """Invoke Josh's image detection Lambda."""

    result = lambda_client.invoke(
        FunctionName=DETECT_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "key": image_key
        }).encode("utf-8")
    )

    if result.get("FunctionError"):
        logger.error(
            "Detection Lambda failed: %s",
            result["FunctionError"]
        )
        raise RuntimeError("Image detection failed.")

    if result.get("StatusCode") != 200:
        raise RuntimeError("Image detection invocation failed.")

    payload = json.loads(
        result["Payload"].read().decode("utf-8")
    )

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid detection response.")

    tags = payload.get("tags")

    if not isinstance(tags, dict):
        raise RuntimeError("Detection response has no valid tags.")

    for tag, count in tags.items():
        if (
            not isinstance(tag, str)
            or not tag.strip()
            or type(count) is not int
            or count < 1
        ):
            raise RuntimeError("Invalid detected tag counts.")

    return tags

def verify_upload(image_key, user_sub):
    """Verify that this temporary image belongs to the user."""

    if not isinstance(image_key, str):
        return False

    if not image_key.startswith("search-temp/"):
        return False

    record = temp_table.get_item(
        Key={"image_key": image_key}
    ).get("Item")

    if not record:
        return False

    if record.get("uploaded_by") != user_sub:
        return False

    if int(record.get("expires_at", 0)) <= int(time.time()):
        return False

    return True


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",)
}


def validate_uploaded_image(image_key):
    """Check that the temporary image exists and is valid."""

    try:
        metadata = s3.head_object(
            Bucket=BUCKET,
            Key=image_key
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in ("404", "NoSuchKey"):
            return False, "Image has not been uploaded yet."

        raise

    content_type = metadata.get("ContentType", "")
    size = metadata.get("ContentLength", 0)

    if content_type not in ALLOWED_IMAGE_TYPES:
        return False, "Only JPEG and PNG images are supported."

    if size <= 0 or size > MAX_IMAGE_SIZE:
        return False, "Image must be between 1 byte and 10 MB."

    # Verify the actual file signature, not just the Content-Type.
    first_bytes = s3.get_object(
        Bucket=BUCKET,
        Key=image_key,
        Range="bytes=0-7"
    )["Body"].read()

    valid_signatures = ALLOWED_IMAGE_TYPES[content_type]

    if not any(
        first_bytes.startswith(signature)
        for signature in valid_signatures
    ):
        return False, "Image content does not match its declared type."

    return True, None
