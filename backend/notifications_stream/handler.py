import json
import os
import boto3

from boto3.dynamodb.types import TypeDeserializer


deserializer = TypeDeserializer()
sns = boto3.client("sns")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

def decode_image(image):
    """Convert a DynamoDB Stream image into a Python dictionary."""
    return {
        key: deserializer.deserialize(value)
        for key, value in image.items()
    }


def lambda_handler(event, context):
    for record in event.get("Records", []):
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue

        dynamodb = record.get("dynamodb", {})

        new_image = decode_image(
            dynamodb.get("NewImage", {})
        )

        old_image = decode_image(
            dynamodb.get("OldImage", {})
        )

        if new_image.get("status") != "done":
            continue

        if old_image.get("status") == "done":
            continue

        tags = new_image.get("tags", {})

        if not tags:
            continue

        message = {
            "event": "image_processing_completed",
            "tags": list(tags.keys())
        }

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject="EcoGuard Animal Notification",
            MessageAttributes={
                "animal_tags": {
                    "DataType": "String.Array",
                    "StringValue": json.dumps(list(tags.keys()))
                }
            }
        )

    return {"statusCode": 200}