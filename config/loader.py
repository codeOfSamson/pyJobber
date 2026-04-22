import json
import os
import boto3


def load_config() -> dict:
    if os.environ.get("ENV") == "production":
        return _load_from_s3()
    return _load_local()


def _load_from_s3() -> dict:
    bucket = os.environ["CONFIG_BUCKET"]
    key = os.environ.get("CONFIG_KEY", "config.json")
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def _load_local() -> dict:
    path = os.environ.get("CONFIG_PATH", "config.json")
    with open(path) as f:
        return json.load(f)
