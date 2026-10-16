
import json
import os
import logging
from urllib.parse import urlparse, unquote

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

table = dynamodb.Table(os.environ["TABLE"])
BUCKET = os.environ["BUCKET"]
FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN", "http://localhost:5173"
)


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin"
        },
        "body": json.dumps(body)
    }


def get_thumbnail_key(thumbnail_url):
    """Extract a thumbnail key from a URL belonging to our S3 bucket."""
    parsed = urlparse(thumbnail_url)

    if parsed.scheme != "https" or not parsed.hostname:
        return None

    # Accept only the configured bucket's S3 virtual-hosted URL.
    allowed_hosts = {
        f"{BUCKET}.s3.ap-southeast-2.amazonaws.com",
        f"{BUCKET}.s3.amazonaws.com"
    }

    if parsed.hostname not in allowed_hosts:
        return None

    key = unquote(parsed.path.lstrip("/"))

    if not key.startswith("thumbnails/"):
        return None

    return key


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
            return response(400, {"error": "Invalid JSON request."})

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be a JSON object."
            })

        thumbnail_url = body.get("thumbnailUrl")

        if not isinstance(thumbnail_url, str):
            return response(400, {
                "error": "thumbnailUrl must be a URL string."
            })

        thumbnail_key = get_thumbnail_key(thumbnail_url)

        if not thumbnail_key:
            return response(400, {
                "error": "Invalid thumbnail URL."
            })

        scan_args = {
            "ProjectionExpression": (
                "file_id, file_type, thumbnail_key, "
                "original_key, uploaded_by, visibility, #st"
            ),
            "ExpressionAttributeNames": {"#st": "status"}
        }

        while True:
            page = table.scan(**scan_args)

            for item in page.get("Items", []):
                if item.get("thumbnail_key") != thumbnail_key:
                    continue

                if item.get("status") != "done":
                    continue

                is_owner = item.get("uploaded_by") == user_sub
                is_public = item.get("visibility") == "public"

                if not (is_owner or is_public):
                    continue

                original_key = item.get("original_key")

                if not original_key:
                    continue

                original_url = s3.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": BUCKET,
                        "Key": original_key
                    },
                    ExpiresIn=900
                )

                return response(200, {
                    "file_id": item["file_id"],
                    "original_url": original_url
                })

            last_key = page.get("LastEvaluatedKey")

            if not last_key:
                break

            scan_args["ExclusiveStartKey"] = last_key

        return response(404, {
            "error": "Thumbnail not found."
        })

    except Exception:
        logger.exception("SearchThumbnailFunction failed")
        return response(500, {
            "error": "Internal server error."
        })
