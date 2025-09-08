import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app


def _h(): return {"x-api-key": os.environ.get("API_KEY","local-test-key-123"), "x-schema-version":"1.3"}


def test_minimal_body_ok(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY","1")
    monkeypatch.setenv("API_KEY","local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/gpt-draft", json={"text":"Hi"}, headers=_h())
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_openapi_has_single_gpt_draft_path():
    with TestClient(app) as c:
        spec = c.get("/openapi.json").json()
    paths = spec["paths"].keys()
    assert "/api/gpt-draft" in paths
    assert "/api/gpt/draft" not in paths
    assert "/api/gpt_draft" not in paths
    assert "/gpt-draft" not in paths
