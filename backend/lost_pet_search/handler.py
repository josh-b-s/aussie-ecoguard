
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

s3 = boto3.client(
    "s3",
    region_name="ap-southeast-2",
    endpoint_url="https://s3.ap-southeast-2.amazonaws.com",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)

table = dynamodb.Table(os.environ["TABLE"])
temp_table = dynamodb.Table(os.environ["TEMP_TABLE"])

BUCKET = os.environ["BUCKET"]
FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
)

MATCH_URL = os.environ.get("MATCH_URL", "")

MAX_CANDIDATES = 20
RECENT_DAYS = 30
PRESIGNED_URL_EXPIRY = 300

def json_converter(value):
    """Convert DynamoDB Decimal values for JSON responses."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )

def response(status_code, body):
    """Return a JSON response with frontend CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin",
        },
        "body": json.dumps(body, default=json_converter),
    }


def get_authenticated_user(event):
    """Read the authenticated Cognito user's ID."""
    claims = (
        (event.get("requestContext") or {})
        .get("authorizer", {})
        .get("claims", {})
    )

    return claims.get("sub")


def get_bearer_token(event):
    """Extract the Cognito token from either header format."""
    headers = event.get("headers") or {}

    for key, value in headers.items():
        if key.lower() == "authorization":
            if isinstance(value, str):
                token = value.strip()

                if token.lower().startswith("bearer "):
                    token = token[7:].strip()

                return token or None

    return None


def verify_upload(image_key, user_sub):
    """Verify that the temporary image belongs to the user."""

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
    """Prevent multiple searches using the same temporary upload."""

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


MAX_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def validate_uploaded_image(image_key):
    """Check that the temporary image exists and is valid."""

    try:
        metadata = s3.head_object(
            Bucket=BUCKET,
            Key=image_key,
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in ("404", "NoSuchKey", "NotFound"):
            return False, "Image has not been uploaded yet."

        raise

    content_type = metadata.get("ContentType", "")
    size = metadata.get("ContentLength", 0)

    if content_type not in ALLOWED_IMAGE_TYPES:
        return False, "Only JPEG and PNG images are supported."

    if size <= 0 or size > MAX_IMAGE_SIZE:
        return False, "Image must be between 1 byte and 10 MB."

    first_bytes = s3.get_object(
        Bucket=BUCKET,
        Key=image_key,
        Range="bytes=0-7",
    )["Body"].read()

    if not any(
        first_bytes.startswith(signature)
        for signature in ALLOWED_IMAGE_TYPES[content_type]
    ):
        return False, "Image content does not match its declared type."

    return True, None


def cleanup_upload(image_key):
    """Delete the temporary image after matching finishes."""

    try:
        s3.delete_object(
            Bucket=BUCKET,
            Key=image_key,
        )
    except ClientError:
        logger.exception(
            "Failed to delete temporary search image."
        )


def get_recent_public_candidates():
    """Find up to 20 recent public images for lost-pet matching."""

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=RECENT_DAYS
    )

    candidates = []
    scan_args = {}

    while True:
        page = table.scan(**scan_args)

        for item in page.get("Items", []):
            if item.get("status") != "done":
                continue

            if item.get("visibility") != "public":
                continue

            if item.get("file_type") != "image":
                continue

            image_key = (
                item.get("thumbnail_key")
                or item.get("original_key")
            )

            if not image_key:
                continue

            uploaded_at = item.get("uploaded_at")

            if not isinstance(uploaded_at, str):
                continue

            try:
                uploaded_time = datetime.fromisoformat(
                    uploaded_at.replace("Z", "+00:00")
                )

                if uploaded_time.tzinfo is None:
                    continue

                if uploaded_time < cutoff:
                    continue

            except ValueError:
                continue

            candidates.append({
                "file_id": item["file_id"],
                "image_key": image_key,
                "uploaded_at": uploaded_at,
                "tags": item.get("tags") or {},
            })

        last_key = page.get("LastEvaluatedKey")

        if not last_key:
            break

        scan_args["ExclusiveStartKey"] = last_key

    candidates.sort(
        key=lambda item: item["uploaded_at"],
        reverse=True,
    )

    return candidates[:MAX_CANDIDATES]


def generate_image_url(image_key):
    """Generate a temporary S3 URL for GCP image matching."""

    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET,
            "Key": image_key,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )


def prepare_match_candidates(candidates):
    """Convert DynamoDB candidates into GCP /match format."""

    return [
        {
            "file_id": candidate["file_id"],
            "url": generate_image_url(candidate["image_key"]),
        }
        for candidate in candidates
    ]


def call_gcp_match(query_url, candidates, id_token):
    """Send images to GCP for similarity matching."""

    if not MATCH_URL:
        raise RuntimeError("GCP matching URL is not configured.")

    payload = {
        "query_url": query_url,
        "candidates": candidates,
    }

    request = Request(
        MATCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=25) as result:
            response_data = json.loads(
                result.read().decode("utf-8")
            )

    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")

        try:
            error_data = json.loads(error_body)
            detail = error_data.get("detail", "")

            if isinstance(detail, str):
                safe_detail = detail if (
                    "http" not in detail.lower()
                    and "token" not in detail.lower()
                    and len(detail) <= 200
                ) else "[redacted]"
            else:
                safe_detail = "[structured validation error]"

        except (ValueError, AttributeError):
            safe_detail = "[non-JSON error response]"

        logger.error(
                "GCP matching service returned HTTP %s; detail: %s",
                exc.code,
                safe_detail,
            )

        raise RuntimeError(
                "GCP matching service rejected the request."
            ) from exc

    except (URLError, TimeoutError) as exc:
        logger.error(
            "GCP matching service connection failed."
        )
        raise RuntimeError(
            "GCP matching service is unavailable."
        ) from exc

    if not isinstance(response_data, dict):
        raise RuntimeError("Invalid GCP matching response.")

    matches = response_data.get("matches")

    if not isinstance(matches, list):
        raise RuntimeError(
            "GCP matching response does not contain matches."
        )

    return response_data


def handler(event, context):
    """Search recent public sightings for a missing pet."""

    try:
        user_sub = get_authenticated_user(event)
        id_token = get_bearer_token(event)

        if not user_sub or not id_token:
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
                "error": "Upload has already been used or expired."
            })

        try:
            candidates = get_recent_public_candidates()

            if not candidates:
                return response(200, {
                    "matches": [],
                    "total": 0,
                    "message": "No recent public sightings found."
                })

            query_url = generate_image_url(image_key)
            match_candidates = prepare_match_candidates(candidates)

            match_data = call_gcp_match(
                query_url,
                match_candidates,
                id_token,
            )

            candidate_lookup = {
                candidate["file_id"]: candidate
                for candidate in candidates
            }

            results = []

            for match in match_data["matches"]:
                if not isinstance(match, dict):
                    continue

                file_id = match.get("file_id")

                if file_id not in candidate_lookup:
                    continue

                candidate = candidate_lookup[file_id]

                results.append({
                    "file_id": file_id,
                    "score": match.get("score"),
                    "uploaded_at": candidate["uploaded_at"],
                    "tags": candidate["tags"],
                    "thumbnail_url": generate_image_url(
                        candidate["image_key"]
                    ),
                })

            return response(200, {
                "matches": results,
                "total": len(results),
                "skipped": match_data.get("skipped", 0),
            })

        finally:
            cleanup_upload(image_key)

    except Exception:
        logger.exception("Lost pet search failed.")

        return response(500, {
            "error": "Lost pet search failed."
        })
