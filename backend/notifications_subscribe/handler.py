
import json
import os

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
        return {
            "statusCode": 403,
            "body": json.dumps({
                "error": "A verified email address is required"
            })
        }

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON body"})
        }

    if not isinstance(body, dict):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid request body"})
        }

    animal_tags = body.get("animal_tags")

    if (
        not isinstance(animal_tags, list)
        or not animal_tags
        or any(
            not isinstance(tag, str) or not tag.strip()
            for tag in animal_tags
        )
    ):
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "animal_tags must be a non-empty list of strings"
            })
        }

    animal_tags = sorted({
        tag.strip().lower() for tag in animal_tags
    })

    table = dynamodb.Table(SUBSCRIPTIONS_TABLE)

    existing = table.get_item(
        Key={"user_id": user_id}
    ).get("Item")

    if existing and existing.get("status") == "pending":
        return {
            "statusCode": 409,
            "body": json.dumps({
                "error": "A subscription is already pending confirmation"
            })
        }

    try:
        table.put_item(
            Item={
                "user_id": user_id,
                "email": email,
                "animal_tags": animal_tags,
                "status": "pending"
            },
            ConditionExpression="attribute_not_exists(user_id)"
        )
    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            return {
                "statusCode": 409,
                "body": json.dumps({
                    "error": "A subscription already exists"
                })
            }
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

    return {
        "statusCode": 202,
        "body": json.dumps({
            "message": "Check your email to confirm the subscription",
            "subscription_arn": response.get("SubscriptionArn")
        })
    }
