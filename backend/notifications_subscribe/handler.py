
import json
import os
import time
import boto3
from botocore.exceptions import ClientError

sns = boto3.client("sns")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

dynamodb = boto3.resource("dynamodb")
SUBSCRIPTIONS_TABLE = os.environ.get("SUBSCRIPTIONS_TABLE")

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173"
)


def api_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }

def find_email_subscriptions(email):
    subscriptions = []
    paginator = sns.get_paginator(
        "list_subscriptions_by_topic"
    )

    for page in paginator.paginate(
        TopicArn=SNS_TOPIC_ARN
    ):
        for subscription in page.get("Subscriptions", []):
            if (
                subscription.get("Protocol") == "email"
                and subscription.get("Endpoint", "").lower()
                == email.lower()
            ):
                subscriptions.append(subscription)

    return subscriptions

def get_subscription_filter_policy(subscription_arn):
    response = sns.get_subscription_attributes(
        SubscriptionArn=subscription_arn
    )

    attributes = response.get("Attributes", {})
    filter_policy = attributes.get("FilterPolicy")

    if not filter_policy:
        return None

    return json.loads(filter_policy)

def subscription_filter_matches(subscription_arn, animal_tags):
    policy = get_subscription_filter_policy(subscription_arn)

    if not isinstance(policy, dict):
        return False

    configured_tags = policy.get("animal_tags")

    if not isinstance(configured_tags, list):
        return False

    return set(configured_tags) == set(animal_tags)

def is_subscription_confirmed(subscription_arn):
    if not (
        isinstance(subscription_arn, str)
        and subscription_arn.startswith("arn:aws:sns:")
    ):
        return False

    response = sns.get_subscription_attributes(
        SubscriptionArn=subscription_arn
    )

    attributes = response.get("Attributes", {})

    return attributes.get("PendingConfirmation") == "false"

def lambda_handler(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )

    email = claims.get("email")
    email_verified = claims.get("email_verified")
    user_id = claims.get("sub")

    if (
        not user_id
        or not email
        or str(email_verified).lower() != "true"
    ):
        return api_response(403, {
            "error": "A verified email address is required"
        })

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return api_response(400, {
            "error": "Invalid JSON body"
        })

    if not isinstance(body, dict):
        return api_response(400, {
            "error": "Invalid request body"
        })

    animal_tags = body.get("animal_tags")

    # 1. Validate the input first
    if (
        not isinstance(animal_tags, list)
        or not animal_tags
        or any(
            not isinstance(tag, str) or not tag.strip()
            for tag in animal_tags
        )
    ):
        return api_response(400, {
            "error": "animal_tags must be a non-empty list of strings"
        })

    # 2. Normalise and remove duplicates
    animal_tags = sorted({
        tag.strip().lower() for tag in animal_tags
    })

    # 3. Check the limit after normalisation
    if len(animal_tags) > 20:
        return api_response(400, {
            "error": "A maximum of 20 animal tags is allowed"
        })

    table = dynamodb.Table(SUBSCRIPTIONS_TABLE)

    existing = table.get_item(
        Key={"user_id": user_id}
    ).get("Item")

    if existing and existing.get("status") == "pending":
        expires_at = existing.get("expires_at", 0)

        if expires_at <= int(time.time()):
            subscriptions = find_email_subscriptions(email)

            confirmed = [
                subscription
                for subscription in subscriptions
                if subscription.get("SubscriptionArn", "").startswith(
                    "arn:aws:sns:"
                )
            ]

            if confirmed:
                for subscription in confirmed:
                    subscription_arn = subscription["SubscriptionArn"]

                    if not is_subscription_confirmed(subscription_arn):
                        return api_response(409, {
                            "error": "SNS subscription is awaiting confirmation"
                        })

                    if subscription_filter_matches(
                        subscription_arn,
                        animal_tags
                    ):
                        return api_response(409, {
                            "error": "An SNS subscription with matching filters already exists"
                        })

                return api_response(409, {
                    "error": "An SNS subscription exists but its filters do not match"
                })

            return api_response(409, {
                "error": "Subscription expired; reconciliation required"
            })

    if existing and existing.get("status") == "pending":
        return api_response(409, {
            "error": "A subscription is already pending confirmation"
        })

    try:
        table.put_item(
            Item={
                "user_id": user_id,
                "email": email,
                "animal_tags": animal_tags,
                "status": "pending",
                "expires_at": int(time.time()) + 86400
            },
            ConditionExpression="attribute_not_exists(user_id)"
        )
    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return api_response(409, {
                "error": "A subscription already exists"
            })
        raise

    try:
        response = sns.subscribe(
            TopicArn=SNS_TOPIC_ARN,
            Protocol="email",
            Endpoint=email,
            ReturnSubscriptionArn=True,
            Attributes={
                "FilterPolicy": json.dumps({
                    "animal_tags": animal_tags
                }),
                "FilterPolicyScope": "MessageAttributes"
            }
        )
    except Exception:
        table.delete_item(
            Key={"user_id": user_id},
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":pending": "pending"
            }
        )
        raise

    subscription_arn = response.get("SubscriptionArn")

    if (
    isinstance(subscription_arn, str)
    and subscription_arn.startswith("arn:aws:sns:")
    ):
        table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET subscription_arn = :arn",
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":arn": subscription_arn,
                ":pending": "pending"
            }
        )

    return api_response(202, {
        "message": "Check your email to confirm the subscription",
        "subscription_arn": response.get("SubscriptionArn")
    })

    
