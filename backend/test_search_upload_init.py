
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_upload_init_requires_authentication():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload_init"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_resource.return_value.Table.return_value = MagicMock()
            mock_client.return_value = MagicMock()

            spec = importlib.util.spec_from_file_location(
                "search_upload_init_auth_test",
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
                    "contentType": "image/jpeg"
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 401

            module.temp_table.put_item.assert_not_called()
            module.s3.generate_presigned_url.assert_not_called()


def test_upload_init_generates_presigned_url():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload_init"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_temp_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_temp_table

            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.generate_presigned_url.return_value = (
                "https://example.com/presigned-upload"
            )

            spec = importlib.util.spec_from_file_location(
                "search_upload_init_success_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {"sub": "current-user"}
                    }
                },
                "body": json.dumps({
                    "contentType": "image/jpeg"
                })
            }

            result = module.handler(event, None)
            body = json.loads(result["body"])

            assert result["statusCode"] == 200
            assert body["expiresIn"] == 300
            assert body["uploadUrl"] == (
                "https://example.com/presigned-upload"
            )

            image_key = body["imageKey"]
            assert image_key.startswith("search-temp/")
            assert image_key.endswith(".jpg")

            mock_s3.generate_presigned_url.assert_called_once()

            args = mock_s3.generate_presigned_url.call_args
            params = args.kwargs["Params"]

            assert args.args[0] == "put_object"
            assert params["Bucket"] == "test-bucket"
            assert params["Key"] == image_key
            assert params["ContentType"] == "image/jpeg"
            assert params["IfNoneMatch"] == "*"
            assert args.kwargs["ExpiresIn"] == 300

            mock_temp_table.put_item.assert_called_once()
            item = mock_temp_table.put_item.call_args.kwargs["Item"]

            assert item["image_key"] == image_key
            assert item["uploaded_by"] == "current-user"
            assert item["expires_at"] > 0

def test_upload_init_rejects_unsupported_file_type():
    handler_path = (
        Path(__file__).resolve().parent
        / "search_upload_init"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "TEMP_TABLE": "test-search-temp",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource, \
             patch("boto3.client") as mock_client:

            mock_resource.return_value.Table.return_value = MagicMock()
            mock_client.return_value = MagicMock()

            spec = importlib.util.spec_from_file_location(
                "search_upload_init_filetype_test",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for content_type in [
                "application/pdf",
                "image/gif",
                "image/svg+xml",
            ]:
                event = {
                    "requestContext": {
                        "authorizer": {
                            "claims": {"sub": "current-user"}
                        }
                    },
                    "body": json.dumps({
                        "contentType": content_type
                    })
                }

                result = module.handler(event, None)

                assert result["statusCode"] == 400, (
                    f"Expected 400 for {content_type}"
                )

            module.s3.generate_presigned_url.assert_not_called()
            module.temp_table.put_item.assert_not_called()
