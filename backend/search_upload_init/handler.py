
import json
import logging
import os
import uuid
import time
import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
temp_table = dynamodb.Table(os.environ["TEMP_TABLE"])

BUCKET = os.environ["BUCKET"]
FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN", "http://localhost:5173"
)

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png"
}


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
            "Vary": "Origin"
        },
        "body": json.dumps(body)
    }


def handler(event, context):
    try:
        claims = (
            (event.get("requestContext") or {})
            .get("authorizer", {})
            .get("claims", {})
        )

        user_sub = claims.get("sub")

        if not user_sub:
            return response(401, {
                "error": "Authentication required."
            })

        try:
            body = json.loads(event.get("body") or "{}")
        except (ValueError, TypeError):
            return response(400, {
                "error": "Invalid JSON request."
            })

        if not isinstance(body, dict):
            return response(400, {
                "error": "Request body must be a JSON object."
            })

        content_type = body.get("contentType")

        if content_type not in ALLOWED_TYPES:
            return response(400, {
                "error": "Only JPEG and PNG images are supported."
            })

        extension = ALLOWED_TYPES[content_type]

        image_key = (
            f"search-temp/{uuid.uuid4().hex}{extension}"
        )

        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET,
                "Key": image_key,
                "ContentType": content_type
            },
            ExpiresIn=300
        )
        
        
        temp_table.put_item(
            Item={
                "image_key": image_key,
                "uploaded_by": user_sub,
                "expires_at": int(time.time()) + 3600
            },
            ConditionExpression="attribute_not_exists(image_key)"
        )


        return response(200, {
            "uploadUrl": upload_url,
            "imageKey": image_key,
            "expiresIn": 300
        })

    except Exception:
        logger.exception("SearchUploadInitFunction failed")
        return response(500, {
            "error": "Internal server error."
        })
