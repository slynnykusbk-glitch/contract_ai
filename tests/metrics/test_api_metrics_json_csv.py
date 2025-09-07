from __future__ import annotations

from importlib import reload

from fastapi.testclient import TestClient


def test_api_metrics_json_csv(monkeypatch):
    monkeypatch.setenv("FEATURE_METRICS", "1")
    import contract_review_app.api.app as api_app
    reload(api_app)
    client = TestClient(api_app.app)

    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    assert resp.json()["schema"] == "1.3"
    assert resp.headers.get("Cache-Control") == "no-store"

    resp_csv = client.get("/api/metrics.csv")
    assert resp_csv.status_code == 200
    assert resp_csv.text.splitlines()[0] == "rule_id,tp,fp,fn,precision,recall,f1"
    assert resp_csv.headers.get("Cache-Control") == "no-store"
