import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def _h():
    return {"x-api-key": os.environ.get("API_KEY", "local-test-key-123"), "x-schema-version": SCHEMA_VERSION}


def _patch(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")


def test_trace_after_analyze(monkeypatch):
    _patch(monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/analyze", json={"text": "hi"}, headers=_h())
        cid = r.headers.get("x-cid")
        assert cid
        r2 = c.get("/api/trace", headers=_h())
        assert cid in r2.json()["cids"]
        r3 = c.get(f"/api/report/{cid}.html", headers=_h())
        assert r3.status_code == 200


def test_report_404_unknown(monkeypatch):
    _patch(monkeypatch)
    with TestClient(app) as c:
        r = c.get("/api/report/unknown.html", headers=_h())
        assert r.status_code == 404
