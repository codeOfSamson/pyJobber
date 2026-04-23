import os
import json
import boto3
from dotenv import load_dotenv


def load_secrets() -> dict:
    if os.environ.get("ENV") == "production":
        return _load_from_secrets_manager()
    return _load_from_env()


def _load_from_env() -> dict:
    dotenv_path = os.environ.get("DOTENV_PATH", ".env")
    load_dotenv(dotenv_path=dotenv_path)
    return {
        "cakeresume_email": os.environ["CAKERESUME_EMAIL"],
        "cakeresume_password": os.environ["CAKERESUME_PASSWORD"],
        "job104_email": os.environ["JOB104_EMAIL"],
        "job104_password": os.environ["JOB104_PASSWORD"],
        "claude_api_key": os.environ["CLAUDE_API_KEY"],
        "db_host": os.environ["DB_HOST"],
        "db_user": os.environ["DB_USER"],
        "db_password": os.environ["DB_PASSWORD"],
        "db_name": os.environ["DB_NAME"],
        "report_email": os.environ["REPORT_EMAIL"],
        "email_password": os.environ["EMAIL_PASSWORD"],
    }


def _load_from_secrets_manager() -> dict:
    secret_name = os.environ["SECRET_NAME"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
