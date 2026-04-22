# tests/test_secrets.py
import json


def test_load_secrets_local(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAKERESUME_EMAIL=cake@test.com\n"
        "CAKERESUME_PASSWORD=pass1\n"
        "JOB104_EMAIL=job@test.com\n"
        "JOB104_PASSWORD=pass2\n"
        "CLAUDE_API_KEY=sk-ant-test\n"
        "DB_HOST=localhost\n"
        "DB_USER=root\n"
        "DB_PASSWORD=dbpass\n"
        "DB_NAME=autojobber\n"
        "REPORT_EMAIL=report@test.com\n"
        "EMAIL_PASSWORD=emailpass\n"
    )
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))

    from secrets.loader import load_secrets
    result = load_secrets()
    assert result["cakeresume_email"] == "cake@test.com"
    assert result["claude_api_key"] == "sk-ant-test"
    assert result["db_host"] == "localhost"


def test_load_secrets_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_NAME", "autojobber/prod")

    secret_data = {
        "cakeresume_email": "prod@cake.com",
        "cakeresume_password": "prodpass",
        "job104_email": "prod@104.com",
        "job104_password": "prodpass2",
        "claude_api_key": "sk-ant-prod",
        "db_host": "rds.endpoint",
        "db_user": "admin",
        "db_password": "rdspass",
        "db_name": "autojobber",
        "report_email": "prod@report.com",
        "email_password": "prodEmailPass",
    }
    from unittest.mock import MagicMock
    mock_sm = MagicMock()
    mock_sm.get_secret_value.return_value = {"SecretString": json.dumps(secret_data)}
    monkeypatch.setattr("boto3.client", lambda service: mock_sm)

    import importlib
    import secrets.loader
    importlib.reload(secrets.loader)
    from secrets.loader import load_secrets
    result = load_secrets()
    assert result["cakeresume_email"] == "prod@cake.com"
    assert result["db_host"] == "rds.endpoint"
