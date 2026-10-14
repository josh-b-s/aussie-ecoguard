import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table(os.environ["TABLE"])


def create_pending(file_id, file_type, original_key, user_id):
    """Insert the file record. Returns False if file_id already exists."""
    item = {
        "file_id": file_id,
        "file_type": file_type,
        "original_key": original_key,
        "uploaded_by": user_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "tags": {},
    }
    try:
        # Conditional put is atomic, so two simultaneous uploads of one file can't both win
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(file_id)")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True
