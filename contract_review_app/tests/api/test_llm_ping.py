import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reload_app():
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)
    return TestClient(app_module.app), modules


@pytest.fixture()
def client():
    client, modules = _reload_app()
    try:
        yield client
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_ping_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("AZURE_KEY_INVALID", raising=False)
    client, modules = _reload_app()
    try:
        r = client.get("/api/llm/ping")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_ping_invalid_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "changeme")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://eastus.example.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    client, modules = _reload_app()
    try:
        r = client.get("/api/llm/ping")
        assert r.status_code == 400
        body = r.json()
        assert body.get("code") == "invalid_llm_key"
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_ping_success(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "a" * 32)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://eastus.example.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.delenv("AZURE_KEY_INVALID", raising=False)
    client, modules = _reload_app()
    try:
        import contract_review_app.llm.provider as provider_mod

        monkeypatch.setattr(
            provider_mod.AzureProvider,
            "ping",
            lambda self: {"ok": True, "latency_ms": 1},
        )
        r = client.get("/api/llm/ping")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_models_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "a" * 32)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://eastus.example.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.setenv("MODEL_DRAFT", "")
    monkeypatch.setenv("MODEL_SUGGEST", "")
    monkeypatch.setenv("MODEL_QA", "")
    monkeypatch.delenv("AZURE_KEY_INVALID", raising=False)
    client, modules = _reload_app()
    try:
        r = client.get("/health")
        assert r.status_code == 200
        models = r.json()["llm"]["models"]
        assert models["draft"] == "gpt-4o-mini"
        assert models["suggest"] == "gpt-4o-mini"
        assert models["qa"] == "gpt-4o-mini"
    finally:
        for m in modules:
            sys.modules.pop(m, None)
