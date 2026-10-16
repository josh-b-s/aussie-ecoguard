
import json
import unittest
from unittest.mock import patch

with patch.dict("os.environ", {
    "TABLE": "test-files-table",
    "BUCKET": "test-media-bucket",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "AWS_DEFAULT_REGION": "ap-southeast-2"
}):
    from search_thumbnail import handler as thumbnail_handler


THUMBNAIL_URL = (
    "https://test-media-bucket.s3.ap-southeast-2.amazonaws.com/"
    "thumbnails/file-001.jpg"
)


class TestSearchThumbnail(unittest.TestCase):

    def setUp(self):
        self.table_patcher = patch.object(thumbnail_handler, "table")
        self.s3_patcher = patch.object(thumbnail_handler, "s3")

        self.mock_table = self.table_patcher.start()
        self.mock_s3 = self.s3_patcher.start()

        self.addCleanup(self.table_patcher.stop)
        self.addCleanup(self.s3_patcher.stop)

        self.mock_s3.generate_presigned_url.return_value = (
            "https://example.com/original.jpg"
        )

    def invoke(self, payload, user_sub="test-user-123"):
        event = {
            "body": json.dumps(payload),
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": user_sub}
                }
            }
        }

        return thumbnail_handler.handler(event, None)

    def test_owner_can_find_original(self):
        self.mock_table.scan.return_value = {
            "Items": [{
                "file_id": "file-001",
                "status": "done",
                "uploaded_by": "test-user-123",
                "visibility": "private",
                "thumbnail_key": "thumbnails/file-001.jpg",
                "original_key": "uploads/file-001.jpg"
            }]
        }

        result = self.invoke({"thumbnailUrl": THUMBNAIL_URL})
        body = json.loads(result["body"])

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["file_id"], "file-001")
        self.assertEqual(
            body["original_url"],
            "https://example.com/original.jpg"
        )

    def test_public_file_accessible(self):
        self.mock_table.scan.return_value = {
            "Items": [{
                "file_id": "file-001",
                "status": "done",
                "uploaded_by": "another-user",
                "visibility": "public",
                "thumbnail_key": "thumbnails/file-001.jpg",
                "original_key": "uploads/file-001.jpg"
            }]
        }

        result = self.invoke({"thumbnailUrl": THUMBNAIL_URL})

        self.assertEqual(result["statusCode"], 200)

    def test_private_file_not_accessible(self):
        self.mock_table.scan.return_value = {
            "Items": [{
                "file_id": "file-001",
                "status": "done",
                "uploaded_by": "another-user",
                "visibility": "private",
                "thumbnail_key": "thumbnails/file-001.jpg",
                "original_key": "uploads/file-001.jpg"
            }]
        }

        result = self.invoke({"thumbnailUrl": THUMBNAIL_URL})

        self.assertEqual(result["statusCode"], 404)
        self.mock_s3.generate_presigned_url.assert_not_called()

    def test_invalid_external_url(self):
        result = self.invoke({
            "thumbnailUrl": "https://another-site.com/image.jpg"
        })

        self.assertEqual(result["statusCode"], 400)
        self.mock_table.scan.assert_not_called()

    def test_missing_authentication(self):
        event = {
            "body": json.dumps({"thumbnailUrl": THUMBNAIL_URL})
        }

        result = thumbnail_handler.handler(event, None)

        self.assertEqual(result["statusCode"], 401)
        self.mock_table.scan.assert_not_called()

    def test_pending_file_excluded(self):
        self.mock_table.scan.return_value = {
            "Items": [{
                "file_id": "file-001",
                "status": "pending",
                "uploaded_by": "test-user-123",
                "thumbnail_key": "thumbnails/file-001.jpg",
                "original_key": "uploads/file-001.jpg"
            }]
        }

        result = self.invoke({"thumbnailUrl": THUMBNAIL_URL})

        self.assertEqual(result["statusCode"], 404)

    def test_presigned_thumbnail_url(self):
        self.mock_table.scan.return_value = {
            "Items": [{
                "file_id": "file-001",
                "status": "done",
                "uploaded_by": "test-user-123",
                "thumbnail_key": "thumbnails/file-001.jpg",
                "original_key": "uploads/file-001.jpg"
            }]
        }

        presigned_url = (
            THUMBNAIL_URL
            + "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
            + "&X-Amz-Signature=example"
        )

        result = self.invoke({"thumbnailUrl": presigned_url})

        self.assertEqual(result["statusCode"], 200)

    def test_cors_header(self):
        result = self.invoke({
            "thumbnailUrl": "https://another-site.com/image.jpg"
        })

        self.assertEqual(
            result["headers"]["Access-Control-Allow-Origin"],
            "http://localhost:5173"
        )


if __name__ == "__main__":
    unittest.main()
