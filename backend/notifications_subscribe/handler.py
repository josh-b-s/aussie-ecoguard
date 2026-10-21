import json
import os

import boto3

sns = boto3.client("sns")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")


def lambda_handler(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )

    email = claims.get("email")
    email_verified = claims.get("email_verified")

    if not email or str(email_verified).lower() != "true":
        return {
            "statusCode": 403,
            "body": json.dumps({
                "error": "A verified email address is required"
            })
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Verified email retrieved successfully"
        })
    }