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

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON body"})
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

    return {
        "statusCode": 202,
        "body": json.dumps({
            "message": "Check your email to confirm the subscription",
            "subscription_arn": response.get("SubscriptionArn")
        })
    }