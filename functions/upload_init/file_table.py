import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table(os.environ["TABLE"])

# Longer than the 5 minute upload URL plus the tagger's 2 minute timeout
STALE_PENDING = timedelta(minutes=10)


def create_pending(file_id, file_type, original_key, user_id, visibility):
    """Insert the file record. Returns False if a live record already exists.

    A failed record, or one pending past STALE_PENDING, is replaced so the upload can be retried.
    """
    now = datetime.now(timezone.utc)
    item = {
        "file_id": file_id,
        "file_type": file_type,
        "original_key": original_key,
        "uploaded_by": user_id,
        "uploaded_at": now.isoformat(),
        "status": "pending",
        "visibility": visibility,
        "tags": {},
    }
    try:
        # Conditional put is atomic, so two simultaneous uploads of one file can't both win
        table.put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(file_id) OR #status = :failed "
                "OR (#status = :pending AND uploaded_at < :cutoff)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":failed": "failed",
                ":pending": "pending",
                ":cutoff": (now - STALE_PENDING).isoformat(),
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True
