import json
import os

import boto3

ssm = boto3.client("ssm")


def load_config():
    """Read per-invocation so a changed parameter applies to the next upload."""
    param = ssm.get_parameter(Name=os.environ["CONFIG_PARAM"])
    return json.loads(param["Parameter"]["Value"])
