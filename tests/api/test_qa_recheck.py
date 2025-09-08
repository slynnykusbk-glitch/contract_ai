import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app


def _h():
    return {
        "x-api-key": os.environ.get("API_KEY", "local-test-key-123"),
        "x-schema-version": "1.3",
    }


def test_minimal_ok(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/qa-recheck", json={"text": "hi"}, headers=_h())
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_validation_messages_are_explicit(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/qa-recheck", json={"text": ""}, headers=_h())
        assert r.status_code in (400, 422)
