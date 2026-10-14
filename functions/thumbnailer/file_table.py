import os

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE"])


def set_thumbnail_key(file_id, thumbnail_key):
    table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET thumbnail_key = :key",
        ExpressionAttributeValues={":key": thumbnail_key},
        ConditionExpression="attribute_exists(file_id)",
    )
