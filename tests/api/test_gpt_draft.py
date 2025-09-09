import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def _h():
    return {"x-api-key": os.environ.get("API_KEY", "local-test-key-123"), "x-schema-version": SCHEMA_VERSION}


def test_minimal_body_ok(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY","1")
    monkeypatch.setenv("API_KEY","local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/gpt-draft", json={"text":"Hi"}, headers=_h())
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_no_legacy_routes():
    with TestClient(app) as c:
        spec = c.get("/openapi.json").json()
        paths = spec["paths"].keys()
        assert "/api/gpt-draft" in paths
        for p in ["/api/gpt/draft", "/api/gpt_draft", "/gpt-draft"]:
            assert p not in paths
            assert c.post(p, json={"text": "Hi"}).status_code == 404
