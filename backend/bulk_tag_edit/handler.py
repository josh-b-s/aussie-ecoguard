import json
import os
import logging
import boto3
from decimal import Decimal
from urllib.parse import urlparse, unquote
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE"])
BUCKET = os.environ["BUCKET"]

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173"
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

def extract_s3_key(url):
    """
    Validate an EcoGuard S3 media URL and extract its object key.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        return None

    if parsed.username or parsed.password or parsed.port:
        return None

    expected_host = (
        f"{BUCKET}.s3.ap-southeast-2.amazonaws.com"
    )

    if parsed.hostname != expected_host:
        return None

    key = unquote(parsed.path.lstrip("/"))

    if not key.startswith("uploads/"):
        return None

    if not key or ".." in key.split("/"):
        return None

    return key

def find_file_record(key):
    """
    Find a DynamoDB file record using its S3 object key.
    """
    filename = key.removeprefix("uploads/")

    file_id, separator, extension = filename.rpartition(".")

    if (
        not separator
        or len(file_id) != 64
        or any(c not in "0123456789abcdef" for c in file_id)
        or not extension
    ):
        return None

    result = table.get_item(
        Key={"file_id": file_id},
        ConsistentRead=True
    )

    item = result.get("Item")

    if not item:
        return None

    # Confirm that the key matches the stored record.
    if item.get("original_key") != key:
        return None

    return item

def update_file_tags(file_id, user_sub, tags, operation):
    """
    Add or remove tags from an owned, processed file.
    Uses optimistic concurrency to avoid overwriting
    another update to the tags.
    """
    requested_tags = set(tags)

    for attempt in range(3):
        result = table.get_item(
            Key={"file_id": file_id},
            ConsistentRead=True
        )

        item = result.get("Item")

        if not item:
            raise ValueError("File not found.")

        if item.get("uploaded_by") != user_sub:
            raise PermissionError("File ownership changed.")

        if item.get("status") != "done":
            raise ValueError("File is not ready.")

        current_tags = item.get("tags") or {}

        if not isinstance(current_tags, dict):
            raise ValueError("Invalid stored tags.")

        updated_tags = current_tags.copy()

        if operation == 1:
            for tag in requested_tags:
                if tag not in updated_tags:
                    updated_tags[tag] = 1
        else:
            for tag in requested_tags:
                updated_tags.pop(tag, None)

        if updated_tags == current_tags:
            return updated_tags

        try:
            table.update_item(
                Key={"file_id": file_id},
                UpdateExpression="SET #tags = :new_tags",
                ConditionExpression=(
                    "attribute_exists(file_id) "
                    "AND uploaded_by = :owner "
                    "AND #status = :done "
                    "AND #tags = :old_tags"
                ),
                ExpressionAttributeNames={
                    "#tags": "tags",
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":new_tags": updated_tags,
                    ":old_tags": current_tags,
                    ":owner": user_sub,
                    ":done": "done"
                }
            )

            return updated_tags

        except ClientError as error:
            if (
                error.response["Error"]["Code"]
                != "ConditionalCheckFailedException"
            ):
                raise

    raise RuntimeError("Concurrent tag update conflict.")

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
        except (json.JSONDecodeError, TypeError):
            return response(400, {
                "error": "Invalid JSON request body."
            })

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be a JSON object."
            })

        urls = body.get("urls")
        tags = body.get("tags")
        operation = body.get("operation")

        if (
            not isinstance(urls, list)
            or not urls
            or len(urls) > 50
            or not all(
                isinstance(url, str) and url.strip()
                for url in urls
            )
        ):
            return response(400, {
                "error": "Provide a non-empty list of media URLs."
            })

        if (
            not isinstance(tags, list)
            or not tags
            or len(tags) > 20
            or not all(
                isinstance(tag, str)
                and tag.strip()
                and len(tag.strip()) <= 50
                for tag in tags
            )
        ):
            return response(400, {
                "error": "Provide a non-empty list of tags."
            })

        if type(operation) is not int or operation not in (0, 1):
            return response(400, {
                "error": "Operation must be 1 (add) or 0 (remove)."
            })

        validated_files = []
        seen_file_ids = set()

        for url in urls:
            key = extract_s3_key(url)

            if not key:
                return response(400, {
                    "error": "Invalid EcoGuard media URL."
                })

            item = find_file_record(key)

            if not item:
                return response(404, {
                    "error": "Media file not found."
                })

            if item.get("uploaded_by") != user_sub:
                return response(403, {
                    "error": "You can only edit your own files."
                })

            if item.get("status") != "done":
                return response(409, {
                    "error": "Media file has not finished processing."
                })

            file_id = item["file_id"]

            if file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                validated_files.append(file_id)

        updated_files = []
        failed_files = []

        for file_id in validated_files:
            try:
                updated_tags = update_file_tags(
                    file_id,
                    user_sub,
                    tags,
                    operation
                )

                updated_files.append({
                    "file_id": file_id,
                    "tags": updated_tags
                })

            except Exception:
                logger.exception(
                    "Failed to update tags for file %s",
                    file_id
                )

                failed_files.append({
                    "file_id": file_id,
                    "error": "Tag update failed."
                })

        status_code = 200 if not failed_files else 207

        return response(status_code, {
            "message": "Bulk tag editing completed.",
            "updated": updated_files,
            "failed": failed_files
        })

    except Exception:
        logger.exception("BulkTagEditFunction failed")
        return response(500, {
            "error": "Internal server error."
        })