import os
from types import SimpleNamespace
from fastapi.testclient import TestClient
import contract_review_app.api.app as app_module
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def _h():
    return {"x-api-key": os.environ.get("API_KEY", "local-test-key-123"), "x-schema-version": SCHEMA_VERSION}


def _patch_env(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")
    def fake_qa(text, rules, timeout_s, profile="smart"):
        return SimpleNamespace(meta={}, items=[])
    monkeypatch.setattr(app_module, "LLM_SERVICE", SimpleNamespace(qa=fake_qa))
    monkeypatch.setattr(app_module.LLM_CONFIG, "mode", "test", raising=False)
    monkeypatch.setattr(app_module.LLM_CONFIG, "provider", "test", raising=False)


def test_minimal_dict_rules_ok(monkeypatch):
    _patch_env(monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/qa-recheck", json={"text": "hi", "rules": {}}, headers=_h())
        assert r.status_code == 200


def test_list_rules_ok_normalized(monkeypatch):
    _patch_env(monkeypatch)
    captured = {}
    def fake_qa(text, rules, timeout_s, profile="smart"):
        captured["rules"] = rules
        return SimpleNamespace(meta={}, items=[])
    monkeypatch.setattr(app_module, "LLM_SERVICE", SimpleNamespace(qa=fake_qa))
    with TestClient(app) as c:
        r = c.post("/api/qa-recheck", json={"text": "hi", "rules": [{"R1": "on"}]}, headers=_h())
        assert r.status_code == 200
        assert captured["rules"] == {"R1": "on"}


def test_empty_text_422_with_details(monkeypatch):
    _patch_env(monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/qa-recheck", json={"text": ""}, headers=_h())
        assert r.status_code == 422
        detail = r.json().get("detail")
        assert isinstance(detail, list) and any("loc" in d and "msg" in d for d in detail)
