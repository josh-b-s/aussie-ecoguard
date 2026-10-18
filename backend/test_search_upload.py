
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

