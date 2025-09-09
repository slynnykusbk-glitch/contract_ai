import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
import contract_review_app.api.app as app_module
import os
from contract_review_app.api.models import SCHEMA_VERSION


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_module.LLM_CONFIG, "provider", "test", raising=False)
    monkeypatch.setattr(app_module.LLM_CONFIG, "mode", "test", raising=False)
    monkeypatch.setattr(app_module.LLM_CONFIG, "valid", True, raising=False)

    def fake_qa(text, rules, timeout_s, profile="smart"):
        return SimpleNamespace(meta={}, items=[{"code": "A"}])

    monkeypatch.setattr(app_module, "LLM_SERVICE", SimpleNamespace(qa=fake_qa))
    return TestClient(app_module.app)


def test_recheck_minimal_ok(client):
    headers = {"x-schema-version": SCHEMA_VERSION}
    flag = os.getenv("FEATURE_REQUIRE_API_KEY", "").strip().lower()
    if flag in {"1", "true", "yes", "on", "enabled"}:
        headers["x-api-key"] = os.getenv("API_KEY", "")
    r = client.post(
        "/api/qa-recheck",
        json={"text": "clause text", "rules": {}, "language": "en-GB"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "qa" in data


def test_recheck_empty_text_422(client):
    headers = {"x-schema-version": SCHEMA_VERSION}
    flag = os.getenv("FEATURE_REQUIRE_API_KEY", "").strip().lower()
    if flag in {"1", "true", "yes", "on", "enabled"}:
        headers["x-api-key"] = os.getenv("API_KEY", "")
    r = client.post(
        "/api/qa-recheck",
        json={"text": "", "rules": {}, "language": "en-GB"},
        headers=headers,
    )
    assert r.status_code == 422
    detail = r.json().get("detail")
    assert isinstance(detail, list)
    assert any("text is empty" in (d.get("msg") or "") for d in detail)
