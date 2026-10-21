import json
from unittest.mock import patch

with patch("boto3.client"):
    from notifications_subscribe.handler import lambda_handler


def test_verified_email_is_accepted():
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com",
                    "email_verified": "true"
                }
            }
        }
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    assert body["message"] == "Verified email retrieved successfully"

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