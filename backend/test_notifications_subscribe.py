import json
from unittest.mock import patch

with patch("boto3.client"):
    from notifications_subscribe.handler import lambda_handler


@patch("notifications_subscribe.handler.sns")
def test_verified_email_is_accepted(mock_sns):
    mock_sns.subscribe.return_value = {
        "SubscriptionArn": "pending confirmation"
    }

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com",
                    "email_verified": "true"
                }
            }
        },
        "body": json.dumps({
            "animal_tags": ["fox", "koala"]
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 202

    mock_sns.subscribe.assert_called_once()

    kwargs = mock_sns.subscribe.call_args.kwargs

    assert kwargs["Protocol"] == "email"
    assert kwargs["Endpoint"] == "test@example.com"
    assert kwargs["ReturnSubscriptionArn"] is True

    assert "Attributes" not in kwargs

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

@patch("notifications_subscribe.handler.sns")
def test_empty_animal_tags_are_rejected(mock_sns):
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com",
                    "email_verified": "true"
                }
            }
        },
        "body": json.dumps({
            "animal_tags": []
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 400

    body = json.loads(result["body"])
    assert body["error"] == (
        "animal_tags must be a non-empty list of strings"
    )

    mock_sns.subscribe.assert_not_called()