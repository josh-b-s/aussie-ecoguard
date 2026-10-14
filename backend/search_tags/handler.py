
import json
import os
import logging
import boto3
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

table = dynamodb.Table(os.environ["TABLE"])
BUCKET = os.environ["BUCKET"]


def json_converter(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    raise TypeError(f"Cannot serialize {type(value).__name__}")


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=json_converter)
    }


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be a JSON object."
            })

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

                # Enable after agreeing on visibility rules:
                # if item.get("visibility") != "public":
                #     continue

                stored_tags = item.get("tags") or {}

                if not isinstance(stored_tags, dict):
                    continue

                matches = all(
                    isinstance(stored_tags.get(tag), (int, Decimal))
                    and stored_tags[tag] >= count
                    for tag, count in requested_tags.items()
                )

                if not matches:
                    continue

                result = {
                    "file_id": item["file_id"],
                    "file_type": item.get("file_type"),
                    "tags": stored_tags
                }

                original_key = item.get("original_key")

                if original_key:
                    result["original_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": original_key
                        },
                        ExpiresIn=900
                    )

                thumbnail_key = item.get("thumbnail_key")

                if thumbnail_key:
                    result["thumbnail_url"] = s3.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": BUCKET,
                            "Key": thumbnail_key
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

    except (ValueError, TypeError, json.JSONDecodeError):
        return response(400, {
            "error": "Invalid JSON request."
        })

    except Exception:
        logger.exception("SearchTagsFunction failed")
        return response(500, {
            "error": "Internal server error."
        })
