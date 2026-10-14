import json
from urllib.parse import unquote_plus


def uploaded_objects(event):
    """Yield (bucket, key) for each object in an S3 event delivered through SNS."""
    for sns_record in event["Records"]:
        s3_event = json.loads(sns_record["Sns"]["Message"])
        # S3 sends a TestEvent with no Records when the notification is first set up
        for record in s3_event.get("Records", []):
            yield (
                record["s3"]["bucket"]["name"],
                unquote_plus(record["s3"]["object"]["key"]),
            )
