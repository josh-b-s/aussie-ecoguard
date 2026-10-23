import json
from unittest.mock import patch
from botocore.exceptions import ClientError
import pytest
with patch("boto3.client"), patch("boto3.resource"):
    from notifications_subscribe.handler import (
    lambda_handler,
    find_email_subscriptions, 
    get_subscription_filter_policy, 
    subscription_filter_matches, 
    is_subscription_confirmed
)


@patch("notifications_subscribe.handler.time.time", return_value=1000000)
@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_verified_email_is_accepted(mock_sns, mock_dynamodb, mock_time):
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

    assert kwargs["Attributes"]["FilterPolicyScope"] == "MessageAttributes"

    filter_policy = json.loads(
        kwargs["Attributes"]["FilterPolicy"]
    )

    assert filter_policy == {
        "animal_tags": ["fox", "koala"]
    }

    mock_dynamodb.Table.assert_called_once()

    mock_dynamodb.Table.return_value.put_item.assert_called_once_with(
        Item={
            "user_id": "test-user-123",
            "email": "test@example.com",
            "animal_tags": ["fox", "koala"],
            "status": "pending", 
            "expires_at": 1086400
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

def test_cors_headers_are_returned():
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {}
            }
        }
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 403

    assert result["headers"]["Access-Control-Allow-Origin"] == (
        "http://localhost:5173"
    )

    assert result["headers"]["Content-Type"] == "application/json"

@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_more_than_20_animal_tags_are_rejected(
    mock_sns, mock_dynamodb
):
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
            "animal_tags": [
                f"animal-{i}" for i in range(21)
            ]
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 400

    body = json.loads(result["body"])
    assert body["error"] == (
        "A maximum of 20 animal tags is allowed"
    )

    mock_sns.subscribe.assert_not_called()
    mock_dynamodb.Table.assert_not_called()

@patch("notifications_subscribe.handler.time.time", return_value=2000000)
@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_expired_pending_subscription(
    mock_sns, mock_dynamodb, mock_time
):
    mock_table = mock_dynamodb.Table.return_value

    mock_table.get_item.return_value = {
        "Item": {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "animal_tags": ["fox"],
            "status": "pending",
            "expires_at": 1000000
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
            "animal_tags": ["koala"]
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 409
    mock_sns.subscribe.assert_not_called()

@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_subscription_arn_is_saved(mock_sns, mock_dynamodb):
    mock_table = mock_dynamodb.Table.return_value
    mock_table.get_item.return_value = {}

    mock_sns.subscribe.return_value = {
        "SubscriptionArn": (
            "arn:aws:sns:ap-southeast-2:123456789012:"
            "ecoguard-animal-notifications:abc123"
        )
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
            "animal_tags": ["fox"]
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 202

    mock_table.update_item.assert_called_once_with(
        Key={"user_id": "test-user-123"},
        UpdateExpression="SET subscription_arn = :arn",
        ConditionExpression="#status = :pending",
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":arn": mock_sns.subscribe.return_value["SubscriptionArn"],
            ":pending": "pending"
        }
    )

@patch("notifications_subscribe.handler.sns")
def test_find_email_subscriptions(mock_sns):
    mock_paginator = mock_sns.get_paginator.return_value

    mock_paginator.paginate.return_value = [
        {
            "Subscriptions": [
                {
                    "Protocol": "email",
                    "Endpoint": "test@example.com",
                    "SubscriptionArn": "arn:subscription-123"
                },
                {
                    "Protocol": "email",
                    "Endpoint": "other@example.com",
                    "SubscriptionArn": "arn:subscription-456"
                }
            ]
        }
    ]

    result = find_email_subscriptions("test@example.com")

    assert len(result) == 1
    assert result[0]["SubscriptionArn"] == "arn:subscription-123"

    mock_sns.get_paginator.assert_called_once_with(
        "list_subscriptions_by_topic"
    )

@patch("notifications_subscribe.handler.sns")
def test_find_confirmed_email_subscription(mock_sns):
    mock_paginator = mock_sns.get_paginator.return_value

    mock_paginator.paginate.return_value = [
        {
            "Subscriptions": [
                {
                    "Protocol": "email",
                    "Endpoint": "test@example.com",
                    "SubscriptionArn": "arn:subscription-123"
                },
                {
                    "Protocol": "email",
                    "Endpoint": "test@example.com",
                    "SubscriptionArn": "PendingConfirmation"
                }
            ]
        }
    ]

    subscriptions = find_email_subscriptions("test@example.com")

    confirmed = [
        subscription
        for subscription in subscriptions
        if subscription.get("SubscriptionArn")
        not in ("PendingConfirmation", "pending confirmation")
    ]

    assert len(confirmed) == 1
    assert confirmed[0]["SubscriptionArn"] == "arn:subscription-123"

@patch("notifications_subscribe.handler.sns")
def test_confirmed_subscription_has_valid_arn(mock_sns):
    mock_paginator = mock_sns.get_paginator.return_value

    mock_paginator.paginate.return_value = [
        {
            "Subscriptions": [
                {
                    "Protocol": "email",
                    "Endpoint": "test@example.com",
                    "SubscriptionArn": (
                        "arn:aws:sns:ap-southeast-2:123456789012:"
                        "ecoguard-animal-notifications:abc123"
                    )
                }
            ]
        }
    ]

    subscriptions = find_email_subscriptions("test@example.com")

    assert len(subscriptions) == 1
    assert subscriptions[0]["SubscriptionArn"].startswith(
        "arn:aws:sns:"
    )

@patch("notifications_subscribe.handler.time.time", return_value=2000000)
@patch("notifications_subscribe.handler.find_email_subscriptions")
@patch("notifications_subscribe.handler.dynamodb")
@patch("notifications_subscribe.handler.sns")
def test_expired_pending_with_confirmed_sns_returns_409(
    mock_sns, mock_dynamodb, mock_find, mock_time
):
    mock_table = mock_dynamodb.Table.return_value

    mock_table.get_item.return_value = {
        "Item": {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "animal_tags": ["fox"],
            "status": "pending",
            "expires_at": 1000000
        }
    }

    mock_find.return_value = [
        {
            "Protocol": "email",
            "Endpoint": "test@example.com",
            "SubscriptionArn": "arn:aws:sns:region:account:topic:abc123"
        }
    ]

    mock_sns.get_subscription_attributes.return_value = {
        "Attributes": {
            "FilterPolicy": json.dumps({
                "animal_tags": ["fox"]
                })
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
            "animal_tags": ["koala"]
        })
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 409
    mock_find.assert_called_once_with("test@example.com")
    mock_sns.subscribe.assert_not_called()
    mock_table.put_item.assert_not_called()

@patch("notifications_subscribe.handler.sns")
def test_get_subscription_filter_policy(mock_sns):
    mock_sns.get_subscription_attributes.return_value = {
        "Attributes": {
            "FilterPolicy": json.dumps({
                "animal_tags": ["fox", "koala"]
            })
        }
    }

    result = get_subscription_filter_policy(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123"
    )

    assert result == {
        "animal_tags": ["fox", "koala"]
    }

    mock_sns.get_subscription_attributes.assert_called_once()

@patch("notifications_subscribe.handler.sns")
def test_get_subscription_filter_policy_missing(mock_sns):
    mock_sns.get_subscription_attributes.return_value = {
        "Attributes": {}
    }

    result = get_subscription_filter_policy(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123"
    )

    assert result is None

@patch("notifications_subscribe.handler.get_subscription_filter_policy")
def test_subscription_filter_matches(mock_get_policy):
    mock_get_policy.return_value = {
        "animal_tags": ["fox", "koala"]
    }

    result = subscription_filter_matches(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123",
        ["koala", "fox"]
    )

    assert result is True

@patch("notifications_subscribe.handler.get_subscription_filter_policy")
def test_subscription_filter_does_not_match(mock_get_policy):
    mock_get_policy.return_value = {
        "animal_tags": ["fox"]
    }

    result = subscription_filter_matches(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123",
        ["koala"]
    )

    assert result is False

@patch("notifications_subscribe.handler.sns")
def test_is_subscription_confirmed(mock_sns):
    mock_sns.get_subscription_attributes.return_value = {
        "Attributes": {
            "PendingConfirmation": "false"
        }
    }

    result = is_subscription_confirmed(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123"
    )

    assert result is True

@patch("notifications_subscribe.handler.sns")
def test_is_subscription_not_confirmed(mock_sns):
    mock_sns.get_subscription_attributes.return_value = {
        "Attributes": {
            "PendingConfirmation": "true"
        }
    }

    result = is_subscription_confirmed(
        "arn:aws:sns:ap-southeast-2:123456789012:topic:abc123"
    )

    assert result is False