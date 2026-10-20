import json

from notifications_stream.handler import lambda_handler


def test_processing_to_done(capsys):
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

    captured = capsys.readouterr().out
    notification = json.loads(captured.strip())

    assert result["statusCode"] == 200
    assert notification["event"] == "image_processing_completed"
    assert notification["tags"] == ["fox"]

def test_already_done_does_not_notify(capsys):
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

    captured = capsys.readouterr().out

    assert result["statusCode"] == 200
    assert captured == ""

def test_still_processing_does_not_notify(capsys):
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

    captured = capsys.readouterr().out

    assert result["statusCode"] == 200
    assert captured == ""