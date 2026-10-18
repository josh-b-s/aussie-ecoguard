
import json
import os
import logging
import boto3
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

table = dynamodb.Table(os.environ["TABLE"])
BUCKET = os.environ["BUCKET"]

DETECT_FUNCTION = os.environ.get(
    "DETECT_FUNCTION",
    "ecoguard-detect"
)

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173"
)


def json_converter(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    raise TypeError(
        f"Cannot serialize {type(value).__name__}"
    )


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin"
        },
        "body": json.dumps(body, default=json_converter)
    }


def detect_tags(image_key):
    """Invoke Josh's image detection Lambda."""

    result = lambda_client.invoke(
        FunctionName=DETECT_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "key": image_key
        }).encode("utf-8")
    )

    if result.get("FunctionError"):
        logger.error(
            "Detection Lambda failed: %s",
            result["FunctionError"]
        )
        raise RuntimeError("Image detection failed.")

    if result.get("StatusCode") != 200:
        raise RuntimeError("Image detection invocation failed.")

    payload = json.loads(
        result["Payload"].read().decode("utf-8")
    )

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid detection response.")

    tags = payload.get("tags")

    if not isinstance(tags, dict):
        raise RuntimeError("Detection response has no valid tags.")

    for tag, count in tags.items():
        if (
            not isinstance(tag, str)
            or not tag.strip()
            or type(count) is not int
            or count < 1
        ):
            raise RuntimeError("Invalid detected tag counts.")

    return tags
