import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def _h():
    return {"x-api-key": os.environ.get("API_KEY", "local-test-key-123"), "x-schema-version": SCHEMA_VERSION}


def _patch(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")


def test_trace_report_flow(monkeypatch):
    _patch(monkeypatch)
    with TestClient(app) as client:
        r = client.post("/api/analyze", json={"text": "hi"}, headers=_h())
        assert r.status_code == 200
        cid = r.headers.get("x-cid")
        assert cid
        assert client.get(f"/api/trace/{cid}", headers=_h()).status_code == 200
        assert client.get(f"/api/trace/{cid}.html", headers=_h()).status_code == 200
        assert client.get(f"/api/report/{cid}.html", headers=_h()).status_code == 200
        assert client.get("/api/trace/bad-cid", headers=_h()).status_code == 404
