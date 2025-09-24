import importlib
import os

from fastapi.testclient import TestClient


def _client(monkeypatch, feature: str | None, key: str | None):
    for var in ["FEATURE_COMPANIES_HOUSE", "CH_API_KEY", "COMPANIES_HOUSE_API_KEY"]:
        monkeypatch.delenv(var, raising=False)
    if feature is not None:
        monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", feature)
    if key is not None:
        monkeypatch.setenv("CH_API_KEY", key)
    import contract_review_app.config as config

    importlib.reload(config)
    import contract_review_app.api.integrations as integrations
    import contract_review_app.api.app as app_module
    import contract_review_app.integrations.companies_house.client as ch_client

    importlib.reload(ch_client)
    ch_client.KEY = os.getenv("CH_API_KEY") or os.getenv("COMPANIES_HOUSE_API_KEY", "")
    importlib.reload(integrations)
    importlib.reload(app_module)
    return TestClient(app_module.app)


def test_companies_health_enabled(monkeypatch):
    client = _client(monkeypatch, "1", "dummy")
    r = client.get("/api/companies/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_companies_health_disabled(monkeypatch):
    client = _client(monkeypatch, None, None)
    r = client.get("/api/companies/health")
    assert r.status_code == 403
    assert r.json().get("status") == "disabled"


def test_companies_health_missing_key(monkeypatch):
    client = _client(monkeypatch, "1", None)
    r = client.get("/api/companies/health")
    assert r.status_code == 400
    assert r.json() == {"error": "companies_house_api_key_missing"}
