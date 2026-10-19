
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_search_upload_requires_authentication():
    handler_path = (
    Path(__file__).resolve().parent
    / "search_upload"
    / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_resource.return_value.Table.return_value = MagicMock()
            mock_client.return_value = MagicMock()

            spec = importlib.util.spec_from_file_location(
                "search_upload_test_handler",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {}
                    }
                },
                "body": json.dumps({
                    "imageKey": "search-temp/example.jpg"
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 401
            assert json.loads(result["body"]) == {
                "error": "Authentication required."
            }

            module.table.scan.assert_not_called()
            module.temp_table.get_item.assert_not_called()
            module.lambda_client.invoke.assert_not_called()


def test_search_upload_rejects_another_users_image():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_dynamodb = mock_resource.return_value
            mock_temp_table = MagicMock()

            def get_table(name):
                if name == "test-search-temp":
                    return mock_temp_table
                return MagicMock()

            mock_dynamodb.Table.side_effect = get_table
            mock_client.return_value = MagicMock()

            spec = importlib.util.spec_from_file_location(
                "search_upload_ownership_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            image_key = "search-temp/" + "a" * 32 + ".jpg"

            mock_temp_table.get_item.return_value = {
                "Item": {
                    "image_key": image_key,
                    "uploaded_by": "another-user",
                    "expires_at": 9999999999
                }
            }

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {
                            "sub": "current-user"
                        }
                    }
                },
                "body": json.dumps({
                    "imageKey": image_key
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 403
            mock_temp_table.get_item.assert_called_once()
            module.lambda_client.invoke.assert_not_called()

def test_search_upload_rejects_expired_image():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_temp_table = MagicMock()

            def get_table(name):
                if name == "test-search-temp":
                    return mock_temp_table
                return MagicMock()

            mock_resource.return_value.Table.side_effect = get_table
            mock_client.return_value = MagicMock()

            spec = importlib.util.spec_from_file_location(
                "search_upload_expiry_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            image_key = "search-temp/" + "b" * 32 + ".jpg"

            mock_temp_table.get_item.return_value = {
                "Item": {
                    "image_key": image_key,
                    "uploaded_by": "current-user",
                    "expires_at": 1000
                }
            }

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {
                            "sub": "current-user"
                        }
                    }
                },
                "body": json.dumps({
                    "imageKey": image_key
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 403

            module.lambda_client.invoke.assert_not_called()
            module.s3.head_object.assert_not_called()
            mock_temp_table.update_item.assert_not_called()


def test_detect_tags_returns_species_counts():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
    }):
        with patch("boto3.resource"), patch("boto3.client"):
            spec = importlib.util.spec_from_file_location(
                "search_upload_detect_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            from io import BytesIO

            module.lambda_client.invoke.return_value = {
                "StatusCode": 200,
                "Payload": BytesIO(
                    json.dumps({
                        "tags": {"fox": 2}
                    }).encode("utf-8")
                )
            }

            image_key = "search-temp/" + "c" * 32 + ".jpg"

            tags = module.detect_tags(image_key)

            assert tags == {"fox": 2}

            module.lambda_client.invoke.assert_called_once()

            invoke_args = module.lambda_client.invoke.call_args.kwargs

            assert invoke_args["InvocationType"] == "RequestResponse"
            assert json.loads(invoke_args["Payload"]) == {
                "key": image_key
            }

def test_search_upload_successful_matching():
    from decimal import Decimal

    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
    }):
        with patch("boto3.resource"), patch("boto3.client"):
            spec = importlib.util.spec_from_file_location(
                "search_upload_success_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            image_key = "search-temp/" + "d" * 32 + ".jpg"

            # Simulate a valid upload and successful detection.
            module.verify_upload = MagicMock(return_value=True)
            module.validate_uploaded_image = MagicMock(
                return_value=(True, None)
            )
            module.claim_upload = MagicMock(return_value=True)
            module.detect_tags = MagicMock(
                return_value={"fox": 2}
            )
            module.cleanup_upload = MagicMock()

            # Simulate DynamoDB records.
            module.table.scan.return_value = {
                "Items": [
                    {
                        "file_id": "file-001",
                        "status": "done",
                        "visibility": "public",
                        "uploaded_by": "another-user",
                        "file_type": "image/jpeg",
                        "tags": {"fox": Decimal("3")},
                        "original_key": "uploads/fox.jpg"
                    },
                    {
                        "file_id": "file-002",
                        "status": "done",
                        "visibility": "private",
                        "uploaded_by": "another-user",
                        "tags": {"fox": Decimal("5")}
                    },
                    {
                        "file_id": "file-003",
                        "status": "pending",
                        "visibility": "public",
                        "uploaded_by": "another-user",
                        "tags": {"fox": Decimal("4")}
                    },
                    {
                        "file_id": "file-004",
                        "status": "done",
                        "visibility": "public",
                        "uploaded_by": "another-user",
                        "tags": {"fox": Decimal("1")}
                    }
                ]
            }

            module.s3.generate_presigned_url.return_value = (
                "https://example.com/fox.jpg"
            )

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {"sub": "current-user"}
                    }
                },
                "body": json.dumps({"imageKey": image_key})
            }

            result = module.handler(event, None)
            body = json.loads(result["body"])

            assert result["statusCode"] == 200
            assert body["detected_tags"] == {"fox": 2}
            assert body["total"] == 1
            assert body["results"][0]["file_id"] == "file-001"

            module.detect_tags.assert_called_once_with(image_key)
            module.cleanup_upload.assert_called_once_with(image_key)
