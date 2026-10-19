
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
