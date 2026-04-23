import json


def test_load_config_local(tmp_path, monkeypatch):
    cfg = {
        "search_terms": ["python"],
        "pages_per_site": 2,
        "sites": ["cakeresume"],
        "remote_only": True,
        "ai_screening": True,
        "report_email": "a@b.com",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(cfg))
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("CONFIG_PATH", str(config_file))

    from config.loader import load_config
    result = load_config()
    assert result["search_terms"] == ["python"]
    assert result["pages_per_site"] == 2


def test_load_config_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("CONFIG_BUCKET", "my-bucket")
    monkeypatch.setenv("CONFIG_KEY", "config.json")

    cfg = {
        "search_terms": ["engineer"],
        "pages_per_site": 3,
        "sites": ["104"],
        "remote_only": False,
        "ai_screening": False,
        "report_email": "x@y.com",
    }

    from unittest.mock import MagicMock
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps(cfg).encode())}
    monkeypatch.setattr("boto3.client", lambda service: mock_s3)

    import importlib
    import config.loader
    importlib.reload(config.loader)
    from config.loader import load_config
    result = load_config()
    assert result["search_terms"] == ["engineer"]
    assert result["pages_per_site"] == 3
