import os

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE"])


def save_tags(file_id, tags):
    _set_status(file_id, "done", tags)


def mark_failed(file_id):
    _set_status(file_id, "failed")


def _set_status(file_id, status, tags=None):
    expression = "SET #status = :status"
    values = {":status": status}
    if tags is not None:
        expression += ", tags = :tags"
        values[":tags"] = tags
    table.update_item(
        Key={"file_id": file_id},
        UpdateExpression=expression,
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=values,
        ConditionExpression="attribute_exists(file_id)",
    )
