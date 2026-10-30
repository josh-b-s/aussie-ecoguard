
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_bulk_tag_edit_rejects_more_than_50_urls():
    handler_path = (
        Path(__file__).resolve().parent
        / "bulk_tag_edit"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table

            spec = importlib.util.spec_from_file_location(
                "bulk_tag_edit_test_handler",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {
                            "sub": "test-user"
                        }
                    }
                },
                "body": json.dumps({
                    "urls": [
                        f"https://example.com/image{i}.jpg"
                        for i in range(51)
                    ],
                    "tags": ["cat"],
                    "operation": 1
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 400
            mock_table.get_item.assert_not_called()
            mock_table.update_item.assert_not_called()


def test_bulk_tag_edit_rejects_more_than_20_tags():
    handler_path = (
        Path(__file__).resolve().parent
        / "bulk_tag_edit"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table

            spec = importlib.util.spec_from_file_location(
                "bulk_tag_edit_test_handler_tags",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {
                            "sub": "test-user"
                        }
                    }
                },
                "body": json.dumps({
                    "urls": ["https://example.com/image.jpg"],
                    "tags": [
                        f"tag{i}" for i in range(21)
                    ],
                    "operation": 1
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 400
            mock_table.get_item.assert_not_called()
            mock_table.update_item.assert_not_called()


def test_bulk_tag_edit_rejects_tags_over_50_characters():
    handler_path = (
        Path(__file__).resolve().parent
        / "bulk_tag_edit"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table

            spec = importlib.util.spec_from_file_location(
                "bulk_tag_edit_test_handler_length",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {
                            "sub": "test-user"
                        }
                    }
                },
                "body": json.dumps({
                    "urls": ["https://example.com/image.jpg"],
                    "tags": ["a" * 51],
                    "operation": 1
                })
            }

            result = module.handler(event, None)

            assert result["statusCode"] == 400
            mock_table.get_item.assert_not_called()
            mock_table.update_item.assert_not_called()


def test_bulk_tag_edit_normalises_tags():
    handler_path = (
        Path(__file__).resolve().parent
        / "bulk_tag_edit"
        / "handler.py"
    )

    with patch.dict(os.environ, {
        "TABLE": "test-files",
        "BUCKET": "test-bucket",
        "FRONTEND_ORIGIN": "http://localhost:5173",
    }):
        with patch("boto3.resource"):
            spec = importlib.util.spec_from_file_location(
                "bulk_tag_edit_test_normalisation",
                handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            event = {
                "requestContext": {
                    "authorizer": {
                        "claims": {"sub": "test-user"}
                    }
                },
                "body": json.dumps({
                    "urls": ["https://example.com/image.jpg"],
                    "tags": [" Cat ", "DOG", "cat"],
                    "operation": 1
                })
            }

            with patch.object(
                module,
                "extract_s3_key",
                return_value="uploads/test.jpg"
            ), patch.object(
                module,
                "find_file_record",
                return_value={
                    "file_id": "test-file",
                    "uploaded_by": "test-user",
                    "status": "done"
                }
            ), patch.object(
                module,
                "update_file_tags",
                return_value={"cat": 1, "dog": 1}
            ) as mock_update:

                result = module.handler(event, None)

                assert result["statusCode"] == 200
                mock_update.assert_called_once_with(
                    "test-file",
                    "test-user",
                    ["cat", "dog"],
                    1
                )

def test_response_serializes_decimal_values():
    import json
    from decimal import Decimal
    from bulk_tag_edit.handler import response

    result = response(200, {
        "tags": {
            "cat": Decimal("1"),
            "animal": Decimal("1"),
            "confidence": Decimal("0.95")
        }
    })

    assert result["statusCode"] == 200

    body = json.loads(result["body"])

    assert body["tags"]["cat"] == 1
    assert body["tags"]["animal"] == 1
    assert body["tags"]["confidence"] == 0.95
