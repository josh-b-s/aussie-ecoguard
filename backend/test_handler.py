
import json
import unittest
from unittest.mock import patch
from decimal import Decimal

# Provide environment variables before importing the handler.
with patch.dict("os.environ", {
    "TABLE": "test-files-table",
    "BUCKET": "test-media-bucket"
}):
    from search_tags import handler as search_handler


class TestSearchTags(unittest.TestCase):

    def setUp(self):
        self.table_patcher = patch.object(search_handler, "table")
        self.s3_patcher = patch.object(search_handler, "s3")

        self.mock_table = self.table_patcher.start()
        self.mock_s3 = self.s3_patcher.start()

        self.addCleanup(self.table_patcher.stop)
        self.addCleanup(self.s3_patcher.stop)

        self.mock_s3.generate_presigned_url.return_value = (
            "https://example.com/test.jpg"
        )


    def invoke(self, payload):
        event = {
            "body": json.dumps(payload),
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "test-user-123"
                    }
                }
            }
        }

        result = search_handler.handler(event, None)
        return result["statusCode"], json.loads(result["body"])

    def test_matching_tags(self):
        self.mock_table.scan.return_value = {
            "Items": [
                {
                    "file_id": "file-001",
                    "file_type": "image",
                    "status": "done",
                    "uploaded_by": "test-user-123",
                    "tags": {
                        "fox": Decimal("3"),
                        "cat": Decimal("1")
                    },
                    "original_key": "uploads/file-001.jpg",
                    "thumbnail_key": "thumbnails/file-001.jpg"
                },
                {
                    "file_id": "file-002",
                    "file_type": "image",
                    "status": "done",
                    "tags": {
                        "fox": Decimal("1")
                    }
                }
            ]
        }

        status, body = self.invoke({"tags": {"fox": 2}})

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["results"][0]["file_id"], "file-001")
        self.assertEqual(body["results"][0]["tags"]["fox"], 3)

    def test_and_matching(self):
        self.mock_table.scan.return_value = {
            "Items": [
                    {
                        "file_id": "file-003",
                        "status": "done",
                        "uploaded_by": "test-user-123",
                        "tags": {
                            "fox": Decimal("2"),
                            "cat": Decimal("1")
                        }
                    },
                {
                    "file_id": "file-004",
                    "status": "done",
                    "tags": {
                        "fox": Decimal("2")
                    }
                }
            ]
        }

        status, body = self.invoke({
            "tags": {"fox": 2, "cat": 1}
        })

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["results"][0]["file_id"], "file-003")

    def test_pending_files_excluded(self):
        self.mock_table.scan.return_value = {
            "Items": [
                {
                    "file_id": "file-005",
                    "status": "pending",
                    "tags": {"fox": Decimal("3")}
                }
            ]
        }

        status, body = self.invoke({"tags": {"fox": 1}})

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)

    def test_invalid_count(self):
        status, body = self.invoke({
            "tags": {"fox": 0}
        })

        self.assertEqual(status, 400)

    def test_empty_tags(self):
        status, body = self.invoke({
            "tags": {}
        })

        self.assertEqual(status, 400)

    def test_pagination(self):
        self.mock_table.scan.side_effect = [
            {
                "Items": [
                  {
                    "file_id": "file-006",
                    "status": "done",
                    "uploaded_by": "test-user-123",
                    "tags": {"fox": Decimal("2")}
                }
                ],
                "LastEvaluatedKey": {"file_id": "file-006"}
            },
            {
                "Items": [
                    {
                        "file_id": "file-007",
                        "status": "done",
                        "uploaded_by": "test-user-123",
                        "tags": {"fox": Decimal("3")}
                    }
                ]
            }
        ]

        status, body = self.invoke({"tags": {"fox": 2}})

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 2)
        self.assertEqual(self.mock_table.scan.call_count, 2)

    
    def test_private_file_excluded(self):
        self.mock_table.scan.return_value = {
            "Items": [
                {
                    "file_id": "private-001",
                    "status": "done",
                    "uploaded_by": "another-user",
                    "visibility": "private",
                    "tags": {"fox": Decimal("2")}
                }
            ]
        }

        status, body = self.invoke({"tags": {"fox": 1}})

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)


    def test_public_file_included(self):
        self.mock_table.scan.return_value = {
            "Items": [
                {
                    "file_id": "public-001",
                    "status": "done",
                    "uploaded_by": "another-user",
                    "visibility": "public",
                    "tags": {"fox": Decimal("2")}
                }
            ]
        }

        status, body = self.invoke({"tags": {"fox": 1}})

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)


    def test_missing_authentication_rejected(self):
        event = {
            "body": json.dumps({"tags": {"fox": 1}})
        }

        result = search_handler.handler(event, None)

        self.assertEqual(result["statusCode"], 401)
        self.mock_table.scan.assert_not_called()


    def test_cors_header_present(self):
        self.mock_table.scan.return_value = {"Items": []}

        event = {
            "body": json.dumps({"tags": {"fox": 1}}),
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "test-user-123"}
                }
            }
        }

        result = search_handler.handler(event, None)

        self.assertEqual(
            result["headers"]["Access-Control-Allow-Origin"],
            "http://localhost:5173"
        )



if __name__ == "__main__":
    unittest.main()
