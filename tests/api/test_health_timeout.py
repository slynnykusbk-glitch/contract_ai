import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from contract_review_app.api import app as app_module


client = TestClient(app_module.app)


def test_health_timeout(monkeypatch):
    async def slow():
        return 0

    loader = SimpleNamespace(rules_count=slow, loaded_packs=slow)
    monkeypatch.setattr(app_module, "rules_loader", loader)
    monkeypatch.setattr(app_module, "rules_registry", None)
    monkeypatch.setattr(app_module, "_RULE_ENGINE_OK", True)
    monkeypatch.setattr(app_module, "_RULE_ENGINE_ERR", "")

    captured: dict[str, float] = {}

    async def fake_wait_for(awaitable, timeout, **_):
        captured["timeout"] = timeout
        await awaitable
        raise asyncio.TimeoutError

    monkeypatch.setattr(app_module.asyncio, "wait_for", fake_wait_for)

    resp = client.get("/health")
    assert resp.status_code == 500
    data = resp.json()
    assert data.get("status") == "error"
    assert data.get("meta", {}).get("rule_engine") == "timeout"
    assert captured["timeout"] == pytest.approx(app_module.RULE_DISCOVERY_TIMEOUT_S)
