from __future__ import annotations

from importlib import reload

from fastapi.testclient import TestClient


def test_metrics_html(monkeypatch):
    monkeypatch.setenv("FEATURE_METRICS", "1")
    import contract_review_app.api.app as api_app
    reload(api_app)
    client = TestClient(api_app.app)
    resp = client.get("/api/metrics.html")
    assert resp.status_code == 200
    assert "<table" in resp.text
    assert "Coverage" in resp.text
    assert resp.headers.get("Cache-Control") == "no-store"
