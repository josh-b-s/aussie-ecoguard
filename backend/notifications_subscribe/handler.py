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

def test_unverified_email_is_rejected():
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com",
                    "email_verified": "false"
                }
            }
        }
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 403

    body = json.loads(result["body"])
    assert body["error"] == "A verified email address is required"