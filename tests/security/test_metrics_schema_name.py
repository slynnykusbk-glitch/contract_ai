from importlib import reload

from fastapi.testclient import TestClient


def test_metrics_schema_name(monkeypatch):
    monkeypatch.setenv("FEATURE_METRICS", "1")
    import contract_review_app.api.app as app_module

    reload(app_module)
    client = TestClient(app_module.app)
    data = client.get("/api/metrics").json()
    assert "schema_version" in data
    assert "schema" not in data
