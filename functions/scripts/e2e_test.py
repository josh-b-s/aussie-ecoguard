"""Upload one file through the pipeline and print the resulting DynamoDB record.

Usage:
    python3 e2e_test.py --api <ApiUrl> --table <TableName> --token <ID token> fox.jpg
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3

CONTENT_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4"}
POLL_SECONDS = 120


def http(request):
    try:
        with urllib.request.urlopen(request) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {request.full_url[:60]}: {e.read().decode()}")


def init_upload(api, token, sha256, content_type):
    body = json.dumps({"contentType": content_type, "sha256": sha256}).encode()
    request = urllib.request.Request(
        f"{api}/upload/init",
        data=body,
        method="POST",
        headers={"Authorization": token, "Content-Type": "application/json"},
    )
    return json.loads(http(request))


def put_file(upload_url, data, content_type):
    http(urllib.request.Request(
        upload_url, data=data, method="PUT", headers={"Content-Type": content_type}
    ))


def is_finished(item, is_image):
    if item.get("status") == "failed":
        return True
    return item.get("status") == "done" and (not is_image or "thumbnail_key" in item)


def wait_for_record(table, file_id, is_image):
    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        item = table.get_item(Key={"file_id": file_id}).get("Item", {})
        if is_finished(item, is_image):
            return item
        time.sleep(3)
    sys.exit(f"Timed out after {POLL_SECONDS}s. Last record: {item}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("file")
    args = parser.parse_args()

    path = Path(args.file)
    content_type = CONTENT_TYPES[path.suffix.lower()]
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()

    result = init_upload(args.api.rstrip("/"), args.token, sha256, content_type)
    print("init:", {k: v for k, v in result.items() if k != "uploadUrl"})

    if not result["duplicate"]:
        put_file(result["uploadUrl"], data, content_type)
        print("uploaded, waiting for processing")

    table = boto3.resource("dynamodb").Table(args.table)
    record = wait_for_record(table, sha256, content_type.startswith("image/"))
    print(json.dumps(record, indent=2, default=str))


if __name__ == "__main__":
    main()
