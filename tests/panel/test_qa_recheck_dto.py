import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
import contract_review_app.api.app as app_module


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
    r = client.post(
        "/api/qa-recheck",
        json={"text": "clause text", "rules": {}},
        headers={"x-schema-version": "1.3"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "qa" in data


def test_recheck_empty_text_422(client):
    r = client.post(
        "/api/qa-recheck",
        json={"text": "", "rules": {}},
        headers={"x-schema-version": "1.3"},
    )
    assert r.status_code == 422
    detail = r.json().get("detail")
    assert isinstance(detail, list)
    assert any("text is empty" in (d.get("msg") or "") for d in detail)
