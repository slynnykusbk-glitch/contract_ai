import importlib

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
    import contract_review_app.api.app as app_module
    importlib.reload(app_module)
    return TestClient(app_module.app)


def test_companies_health_enabled(monkeypatch):
    client = _client(monkeypatch, "1", "dummy")
    r = client.get("/api/companies/health")
    assert r.status_code == 200
    assert r.json() == {"companies_house": "ok"}


def test_companies_health_disabled(monkeypatch):
    client = _client(monkeypatch, None, None)
    r = client.get("/api/companies/health")
    assert r.status_code == 403
    assert r.json().get("status") == "disabled"
