import asyncio
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from contract_review_app.api import app as app_module


client = TestClient(app_module.app)


def test_health_timeout(monkeypatch):
    async def slow():
        await asyncio.sleep(app_module.RULE_DISCOVERY_TIMEOUT_S + 1)

    loader = SimpleNamespace(rules_count=slow, loaded_packs=slow)
    monkeypatch.setattr(app_module, "rules_loader", loader)
    monkeypatch.setattr(app_module, "rules_registry", None)
    monkeypatch.setattr(app_module, "_RULE_ENGINE_OK", True)
    monkeypatch.setattr(app_module, "_RULE_ENGINE_ERR", "")

    start = time.time()
    resp = client.get("/health")
    elapsed = time.time() - start
    assert elapsed < app_module.RULE_DISCOVERY_TIMEOUT_S + 0.5
    assert resp.status_code == 500
    data = resp.json()
    assert data.get("status") == "error"
    assert data.get("meta", {}).get("rule_engine") == "timeout"

