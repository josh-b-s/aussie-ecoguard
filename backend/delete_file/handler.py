import json
import os
import logging
import boto3
import re
import uuid
import time
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE = os.environ["TABLE"]
BUCKET = os.environ["BUCKET"]

table = dynamodb.Table(TABLE)

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173"
)
DELETION_LOCK_TIMEOUT = 300  # 5 minutes

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin"
        },
        "body": json.dumps(body)
    }

def get_user_sub(event):
    """
    Extract the authenticated user's Cognito ID.
    """
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    claims = authorizer.get("claims") or {}

    return claims.get("sub")

def get_file_record(file_id):
    """
    Retrieve a file record from DynamoDB.
    """
    result = table.get_item(
        Key={"file_id": file_id},
        ConsistentRead=True
    )

    return result.get("Item")

def validate_s3_keys(file_id, item):
    """
    Validate the original and thumbnail S3 object keys.
    """
    original_key = item.get("original_key")
    thumbnail_key = item.get("thumbnail_key")

    if not isinstance(original_key, str):
        return None

    if not original_key.startswith(f"uploads/{file_id}."):
        return None

    if "/" in original_key.removeprefix("uploads/"):
        return None

    if thumbnail_key is not None:
        if not isinstance(thumbnail_key, str):
            return None

        if not thumbnail_key.startswith(f"thumbnails/{file_id}."):
            return None

        if "/" in thumbnail_key.removeprefix("thumbnails/"):
            return None

    return {
        "original_key": original_key,
        "thumbnail_key": thumbnail_key
    }

def is_valid_file_id(file_id):
    """
    Check that the file ID is a 64-character SHA-256 hex string.
    """
    return (
        isinstance(file_id, str)
        and re.fullmatch(r"[0-9a-f]{64}", file_id) is not None
    )

def mark_file_deleting(file_id, user_sub, keys, deletion_id):
    """
    Acquire or recover a deletion lock while verifying
    ownership and confirming that S3 keys have not changed.
    """
    now = int(time.time())
    stale_before = now - DELETION_LOCK_TIMEOUT

    condition = (
        "attribute_exists(file_id) "
        "AND uploaded_by = :owner "
        "AND original_key = :original_key "
        "AND ("
        "#status = :done "
        "OR ("
        "#status = :deleting "
        "AND deletion_started_at <= :stale_before"
        ")"
        ")"
    )

    values = {
        ":owner": user_sub,
        ":done": "done",
        ":deleting": "deleting",
        ":original_key": keys["original_key"],
        ":deletion_id": deletion_id,
        ":deletion_started_at": now,
        ":stale_before": stale_before
    }

    if keys["thumbnail_key"] is None:
        condition += " AND attribute_not_exists(thumbnail_key)"
    else:
        condition += " AND thumbnail_key = :thumbnail_key"
        values[":thumbnail_key"] = keys["thumbnail_key"]

    table.update_item(
        Key={"file_id": file_id},
        UpdateExpression=(
            "SET #status = :deleting, "
            "deletion_id = :deletion_id, "
            "deletion_started_at = :deletion_started_at"
        ),
        ConditionExpression=condition,
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues=values
    )

def delete_s3_objects(keys):
    """
    Delete the original file and its thumbnail from S3.
    """
    object_keys = [keys["original_key"]]

    if keys["thumbnail_key"]:
        object_keys.append(keys["thumbnail_key"])

    for object_key in object_keys:
        s3.delete_object(
            Bucket=BUCKET,
            Key=object_key
        )

def delete_file_record(file_id, user_sub, deletion_id):
    """
    Remove the DynamoDB record only if this deletion
    attempt still owns the lock.
    """
    table.delete_item(
        Key={"file_id": file_id},
        ConditionExpression=(
            "attribute_exists(file_id) "
            "AND uploaded_by = :owner "
            "AND #status = :deleting "
            "AND deletion_id = :deletion_id"
        ),
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":owner": user_sub,
            ":deleting": "deleting",
            ":deletion_id": deletion_id
        }
    )

def is_deletion_stalled(item):
    """
    Check whether a deletion has exceeded the
    configured timeout.
    """
    if item.get("status") != "deleting":
        return False

    started_at = item.get("deletion_started_at")

    if started_at is None:
        return False

    try:
        elapsed = time.time() - int(started_at)
    except (TypeError, ValueError, OverflowError):
        return False

    return elapsed >= DELETION_LOCK_TIMEOUT

def lambda_handler(event, context):
    """
    Handle authenticated file deletion requests.
    """

    # 1. Identify the authenticated user
    user_sub = get_user_sub(event)

    if not user_sub:
        return response(401, {
            "error": "Authentication required."
        })

    # 2. Extract the requested file ID
    path_parameters = event.get("pathParameters") or {}
    file_id = path_parameters.get("file_id")

    if not is_valid_file_id(file_id):
        return response(400, {
            "error": "Invalid file ID."
        })

    # 3. Retrieve the file record
    try:
        item = get_file_record(file_id)
    except ClientError:
        logger.exception("Failed to retrieve file record")
        return response(500, {
            "error": "Unable to retrieve file."
        })

    if not item:
        return response(404, {
            "error": "File not found."
        })

    # 4. Verify file ownership
    if item.get("uploaded_by") != user_sub:
        return response(403, {
            "error": "You can only delete your own files."
        })

    # 5. Validate S3 object keys
    keys = validate_s3_keys(file_id, item)

    if keys is None:
        return response(500, {
            "error": "Invalid file storage information."
        })

    # 6. Mark the file as deleting
    deletion_id = str(uuid.uuid4())

    try:
        mark_file_deleting(file_id, user_sub, keys, deletion_id)
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return response(409, {
                "error": "File cannot be deleted in its current state."
            })

        logger.exception("Failed to mark file as deleting")
        return response(500, {
            "error": "Unable to begin file deletion."
        })

    # 7. Delete the S3 objects
    try:
        delete_s3_objects(keys)
    except ClientError:
        logger.exception("Failed to delete S3 objects")
        return response(500, {
            "error": "File deletion was interrupted."
        })

    # 8. Delete the DynamoDB record
    try:
        delete_file_record(file_id, user_sub, deletion_id)
    except ClientError:
        logger.exception("Failed to delete DynamoDB record")
        return response(500, {
            "error": "File deletion was interrupted."
        })

    return response(200, {
        "message": "File deleted successfully.",
        "file_id": file_id
    })