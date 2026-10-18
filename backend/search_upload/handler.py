
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


def claim_upload(image_key, user_sub):
    """Allow only one search attempt per upload session."""

    try:
        temp_table.update_item(
            Key={"image_key": image_key},
            UpdateExpression="SET #state = :used",
            ConditionExpression=(
                "attribute_exists(image_key) "
                "AND uploaded_by = :owner "
                "AND expires_at > :now "
                "AND attribute_not_exists(#state)"
            ),
            ExpressionAttributeNames={
                "#state": "state"
            },
            ExpressionAttributeValues={
                ":used": "used",
                ":owner": user_sub,
                ":now": int(time.time())
            }
        )
        return True

    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


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


def handler(event, context):
    try:
        claims = (
            (event.get("requestContext") or {})
            .get("authorizer", {})
            .get("claims", {})
        )

        user_sub = claims.get("sub")

        if not user_sub:
            return response(401, {
                "error": "Authentication required."
            })

        try:
            body = json.loads(event.get("body") or "{}")
        except (ValueError, TypeError):
            return response(400, {
                "error": "Invalid JSON request."
            })

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be a JSON object."
            })

        image_key = body.get("imageKey")

        if not isinstance(image_key, str):
            return response(400, {
                "error": "imageKey must be a string."
            })

        if not verify_upload(image_key, user_sub):
            return response(403, {
                "error": "Upload not found, expired, or unauthorized."
            })

        valid, error_message = validate_uploaded_image(image_key)

        if not valid:
            return response(400, {
                "error": error_message
            })

        if not claim_upload(image_key, user_sub):
            return response(409, {
                "error": "Upload has already been used or has expired."
            })

        try:
            detected_tags = detect_tags(image_key)
        except Exception:
            logger.exception("Image detection failed")
            return response(502, {
                "error": "Image detection service failed."
            })

        if not detected_tags:
            return response(200, {
                "detected_tags": {},
                "results": [],
                "total": 0
            })

        results = []
        scan_args = {}

        while True:
            page = table.scan(**scan_args)

            for item in page.get("Items", []):
                if item.get("status") != "done":
                    continue

                is_owner = item.get("uploaded_by") == user_sub
                is_public = item.get("visibility") == "public"

                if not (is_owner or is_public):
                    continue

                stored_tags = item.get("tags") or {}

                if not isinstance(stored_tags, dict):
                    continue

                matches = all(
                    isinstance(stored_tags.get(tag), (int, Decimal))
                    and stored_tags[tag] >= count
                    for tag, count in detected_tags.items()
                )

                if not matches:
                    continue

                result = {
                    "file_id": item["file_id"],
                    "file_type": item.get("file_type"),
                    "tags": stored_tags
                }

                original_key = item.get("original_key")

                if original_key:
                    result["original_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": original_key
                        },
                        ExpiresIn=900
                    )

                thumbnail_key = item.get("thumbnail_key")

                if thumbnail_key:
                    result["thumbnail_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": thumbnail_key
                        },
                        ExpiresIn=900
                    )

                results.append(result)

            last_key = page.get("LastEvaluatedKey")

            if not last_key:
                break

            scan_args["ExclusiveStartKey"] = last_key

        return response(200, {
            "detected_tags": detected_tags,
            "results": results,
            "total": len(results)
        })

    except Exception:
        logger.exception("SearchUploadFunction failed")
        return response(500, {
            "error": "Internal server error."
        })

