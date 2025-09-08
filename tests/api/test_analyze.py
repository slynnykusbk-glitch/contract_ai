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
        r = c.post("/api/analyze", json={"text": "Hello"}, headers=_h())
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_validation_message_contains_loc_and_msg(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/analyze", json={"text": None}, headers=_h())
        assert r.status_code == 422
        detail = r.json().get("detail")
        assert isinstance(detail, list) and any(
            "loc" in e and "msg" in e for e in detail
        )
