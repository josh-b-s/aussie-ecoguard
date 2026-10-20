import json

from boto3.dynamodb.types import TypeDeserializer


deserializer = TypeDeserializer()


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

        print(json.dumps({
            "event": "image_processing_completed",
            "tags": list(tags.keys())
        }))

    return {"statusCode": 200}