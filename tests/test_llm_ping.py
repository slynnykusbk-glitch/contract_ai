import importlib
import sys
from fastapi.testclient import TestClient


def reload_app():
    for mod in ["contract_review_app.api", "contract_review_app.api.app"]:
        sys.modules.pop(mod, None)
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)
    return TestClient(app_module.app)


def test_llm_ping_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    client = reload_app()
    r = client.get("/api/llm/ping")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_llm_ping_invalid_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    client = reload_app()
    r = client.get("/api/llm/ping")
    assert r.status_code == 400
    body = r.json()
    assert body.get("code") == "invalid_llm_key"
