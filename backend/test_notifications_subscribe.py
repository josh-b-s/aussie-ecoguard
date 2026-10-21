import json
from unittest.mock import patch
from botocore.exceptions import ClientError

with patch("boto3.client"), patch("boto3.resource"):
    from notifications_subscribe.handler import lambda_handler


@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_verified_email_is_accepted(mock_sns, mock_dynamodb):
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
    mock_dynamodb.Table.assert_called_once()

    mock_dynamodb.Table.return_value.put_item.assert_called_once_with(
        Item={
            "user_id": "test-user-123",
            "email": "test@example.com",
            "animal_tags": ["fox", "koala"],
            "status": "pending"
        },
        ConditionExpression="attribute_not_exists(user_id)"
    )

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

@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_existing_pending_subscription_is_rejected(
    mock_sns, mock_dynamodb
):
    mock_table = mock_dynamodb.Table.return_value

    mock_table.get_item.return_value = {
        "Item": {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "animal_tags": ["fox"],
            "status": "pending"
        }
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

    assert result["statusCode"] == 409
    mock_sns.subscribe.assert_not_called()
    mock_table.put_item.assert_not_called()

@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_concurrent_subscription_returns_409(mock_sns, mock_dynamodb):
    mock_table = mock_dynamodb.Table.return_value

    mock_table.get_item.return_value = {}

    mock_table.put_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Conditional request failed"
            }
        },
        "PutItem"
    )

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

    assert result["statusCode"] == 409
    mock_table.put_item.assert_called_once()
    mock_sns.subscribe.assert_not_called()

@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_sns_failure_cleans_up_pending_record(
    mock_sns, mock_dynamodb
):
    mock_table = mock_dynamodb.Table.return_value
    mock_table.get_item.return_value = {}

    mock_sns.subscribe.side_effect = RuntimeError(
        "SNS temporarily unavailable"
    )

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
            "animal_tags": ["fox"]
        })
    }

    with pytest.raises(
        RuntimeError,
        match="SNS temporarily unavailable"
    ):
        lambda_handler(event, None)

    mock_table.delete_item.assert_called_once_with(
        Key={"user_id": "test-user-123"},
        ConditionExpression="#status = :pending",
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":pending": "pending"
        }
    )