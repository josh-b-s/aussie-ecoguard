
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
