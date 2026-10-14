
import json
import os
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

table = dynamodb.Table(os.environ["TABLE"])
BUCKET = os.environ["BUCKET"]


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str)
    }


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        requested_tags = body.get("tags")

        if not isinstance(requested_tags, dict) or not requested_tags:
            return response(400, {
                "error": "Provide a non-empty tags object."
            })

        for tag, count in requested_tags.items():
            if (
                not isinstance(tag, str)
                or not tag.strip()
                or type(count) is not int
                or count < 1
            ):
                return response(400, {
                    "error": "Tags must have positive integer counts."
                })

        results = []
        scan_args = {}

        while True:
            page = table.scan(**scan_args)

            for item in page.get("Items", []):
                if item.get("status") != "done":
                    continue

                stored_tags = item.get("tags", {})

                matches = all(
                    stored_tags.get(tag, 0) >= count
                    for tag, count in requested_tags.items()
                )

                if not matches:
                    continue

                result = {
                    "file_id": item["file_id"],
                    "file_type": item.get("file_type"),
                    "tags": stored_tags
                }

                if item.get("original_key"):
                    result["original_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": item["original_key"]
                        },
                        ExpiresIn=900
                    )

                if item.get("thumbnail_key"):
                    result["thumbnail_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": item["thumbnail_key"]
                        },
                        ExpiresIn=900
                    )

                results.append(result)

            if "LastEvaluatedKey" not in page:
                break

            scan_args["ExclusiveStartKey"] = page["LastEvaluatedKey"]

        return response(200, {
            "results": results,
            "total": len(results)
        })

    except (ValueError, TypeError):
        return response(400, {
            "error": "Invalid JSON request."
        })
    except Exception:
        return response(500, {
            "error": "Internal server error."
        })
