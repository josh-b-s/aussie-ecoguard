import json

from notifications_stream.handler import lambda_handler


from unittest.mock import patch


@patch("notifications_stream.handler.sns")
def test_processing_to_done(mock_sns):
    event = {
        "Records": [
            {
                "eventName": "MODIFY",
                "dynamodb": {
                    "OldImage": {
                        "status": {"S": "processing"}
                    },
                    "NewImage": {
                        "status": {"S": "done"},
                        "tags": {
                            "M": {
                                "fox": {"N": "1"}
                            }
                        }
                    }
                }
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_sns.publish.assert_called_once()

    publish_args = mock_sns.publish.call_args.kwargs

    message = json.loads(publish_args["Message"])

    assert message["event"] == "image_processing_completed"
    assert message["tags"] == ["fox"]

    attributes = publish_args["MessageAttributes"]
    assert attributes["animal_tags"]["DataType"] == "String.Array"
    assert json.loads(
        attributes["animal_tags"]["StringValue"]
    ) == ["fox"]

@patch("notifications_stream.handler.sns")
def test_already_done_does_not_notify(mock_sns):
    event = {
        "Records": [
            {
                "eventName": "MODIFY",
                "dynamodb": {
                    "OldImage": {
                        "status": {"S": "done"}
                    },
                    "NewImage": {
                        "status": {"S": "done"},
                        "tags": {
                            "M": {
                                "fox": {"N": "1"}
                            }
                        }
                    }
                }
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_sns.publish.assert_not_called()

@patch("notifications_stream.handler.sns")
def test_still_processing_does_not_notify(mock_sns):
    event = {
        "Records": [
            {
                "eventName": "MODIFY",
                "dynamodb": {
                    "OldImage": {
                        "status": {"S": "pending"}
                    },
                    "NewImage": {
                        "status": {"S": "processing"},
                        "tags": {
                            "M": {
                                "fox": {"N": "1"}
                            }
                        }
                    }
                }
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    mock_sns.publish.assert_not_called()