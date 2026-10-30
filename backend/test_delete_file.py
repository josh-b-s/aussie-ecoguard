import sys
import importlib
from unittest.mock import Mock
from botocore.exceptions import ClientError
import boto3
import pytest


@pytest.fixture
def handler_module(monkeypatch):
    # Provide test environment variables
    monkeypatch.setenv("TABLE", "TestFilesTable")
    monkeypatch.setenv("BUCKET", "test-ecoguard-bucket")
    monkeypatch.setenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173"
    )

    # Mock DynamoDB
    mock_table = Mock()
    mock_dynamodb = Mock()
    mock_dynamodb.Table.return_value = mock_table

    # Mock S3
    mock_s3 = Mock()

    monkeypatch.setattr(
        boto3,
        "resource",
        Mock(return_value=mock_dynamodb)
    )

    monkeypatch.setattr(
        boto3,
        "client",
        Mock(return_value=mock_s3)
    )

    # Import the handler using mocked AWS services
    sys.modules.pop("delete_file.handler", None)

    module = importlib.import_module("delete_file.handler")

    yield module

    sys.modules.pop("delete_file.handler", None)

def test_delete_file_requires_authentication(handler_module):
    result = handler_module.lambda_handler({}, None)

    assert result["statusCode"] == 401


def test_delete_file_rejects_invalid_file_id(handler_module):
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123"
                }
            }
        },
        "pathParameters": {
            "file_id": "invalid-id"
        }
    }

    result = handler_module.lambda_handler(event, None)

    assert result["statusCode"] == 400


def test_delete_file_returns_404_when_not_found(handler_module):
    module = handler_module

    module.get_file_record = Mock(return_value=None)

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123"
                }
            }
        },
        "pathParameters": {
            "file_id": "a" * 64
        }
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 404


def test_delete_file_rejects_other_user(handler_module):
    module = handler_module

    module.get_file_record = Mock(return_value={
        "file_id": "a" * 64,
        "uploaded_by": "another-user",
        "original_key": f"uploads/{'a' * 64}.jpg",
        "thumbnail_key": f"thumbnails/{'a' * 64}.jpg",
        "status": "done"
    })

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123"
                }
            }
        },
        "pathParameters": {
            "file_id": "a" * 64
        }
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 403
    module.s3.delete_object.assert_not_called()

def test_delete_file_rejects_invalid_s3_keys(handler_module):
    module = handler_module
    file_id = "a" * 64

    module.get_file_record = Mock(return_value={
        "file_id": file_id,
        "uploaded_by": "test-user-123",
        "original_key": "uploads/another-file.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg",
        "status": "done"
    })

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "test-user-123"}
            }
        },
        "pathParameters": {"file_id": file_id}
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 500
    module.s3.delete_object.assert_not_called()


def test_delete_file_successfully(handler_module):
    module = handler_module
    file_id = "a" * 64

    module.get_file_record = Mock(return_value={
        "file_id": file_id,
        "uploaded_by": "test-user-123",
        "original_key": f"uploads/{file_id}.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg",
        "status": "done"
    })

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "test-user-123"}
            }
        },
        "pathParameters": {"file_id": file_id}
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 200

    assert module.s3.delete_object.call_count == 2

    module.table.update_item.assert_called_once()
    module.table.delete_item.assert_called_once()

    update_args = module.table.update_item.call_args.kwargs
    assert update_args["ExpressionAttributeValues"][":deletion_id"]

    delete_args = module.table.delete_item.call_args.kwargs
    assert (
        delete_args["ExpressionAttributeValues"][":deletion_id"]
        == update_args["ExpressionAttributeValues"][":deletion_id"]
    )

def test_delete_file_preserves_record_when_s3_fails(handler_module):
    module = handler_module
    file_id = "a" * 64

    module.get_file_record = Mock(return_value={
        "file_id": file_id,
        "uploaded_by": "test-user-123",
        "original_key": f"uploads/{file_id}.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg",
        "status": "done"
    })

    module.s3.delete_object.side_effect = ClientError(
        {
            "Error": {
                "Code": "InternalError",
                "Message": "Simulated S3 failure"
            }
        },
        "DeleteObject"
    )

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "test-user-123"}
            }
        },
        "pathParameters": {"file_id": file_id}
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 500

    # DynamoDB record must not be deleted.
    module.table.delete_item.assert_not_called()

def test_delete_file_handles_dynamodb_cleanup_failure(handler_module):
    module = handler_module
    file_id = "a" * 64

    module.get_file_record = Mock(return_value={
        "file_id": file_id,
        "uploaded_by": "test-user-123",
        "original_key": f"uploads/{file_id}.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg",
        "status": "done"
    })

    module.table.delete_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "InternalError",
                "Message": "Simulated DynamoDB failure"
            }
        },
        "DeleteItem"
    )

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "test-user-123"}
            }
        },
        "pathParameters": {"file_id": file_id}
    }

    result = module.lambda_handler(event, None)

    assert result["statusCode"] == 500

    # Both S3 deletion requests should have succeeded.
    assert module.s3.delete_object.call_count == 2

    # DynamoDB cleanup was attempted.
    module.table.delete_item.assert_called_once()

def test_stalled_deletion_can_be_recovered(handler_module):
    module = handler_module

    file_id = "a" * 64
    keys = {
        "original_key": f"uploads/{file_id}.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg"
    }

    module.mark_file_deleting(
        file_id,
        "test-user-123",
        keys,
        "new-deletion-id"
    )

    args = module.table.update_item.call_args.kwargs

    assert args["ExpressionAttributeValues"][":deleting"] == "deleting"
    assert ":stale_before" in args["ExpressionAttributeValues"]


def test_recent_deletion_lock_is_not_recovered(handler_module):
    module = handler_module

    file_id = "a" * 64
    keys = {
        "original_key": f"uploads/{file_id}.jpg",
        "thumbnail_key": f"thumbnails/{file_id}.jpg"
    }

    # The conditional update must require the previous
    # deletion timestamp to be older than the threshold.
    module.mark_file_deleting(
        file_id,
        "test-user-123",
        keys,
        "new-deletion-id"
    )

    args = module.table.update_item.call_args.kwargs

    assert "deletion_started_at <= :stale_before" in (
        args["ConditionExpression"]
    )