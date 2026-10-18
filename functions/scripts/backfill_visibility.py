"""Set visibility on records created before the field existed.

Usage: python3 backfill_visibility.py <table> [public|private]
"""
import sys

import boto3


def main():
    table_name = sys.argv[1]
    visibility = sys.argv[2] if len(sys.argv) > 2 else "public"
    if visibility not in ("public", "private"):
        sys.exit("visibility must be public or private")

    table = boto3.resource("dynamodb").Table(table_name)
    scan = {
        "FilterExpression": "attribute_not_exists(visibility)",
        "ProjectionExpression": "file_id",
    }
    updated = 0
    while True:
        page = table.scan(**scan)
        for item in page["Items"]:
            table.update_item(
                Key={"file_id": item["file_id"]},
                UpdateExpression="SET visibility = :v",
                ConditionExpression="attribute_not_exists(visibility)",
                ExpressionAttributeValues={":v": visibility},
            )
            updated += 1
        if "LastEvaluatedKey" not in page:
            break
        scan["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    print(f"set visibility={visibility} on {updated} records")


main()
