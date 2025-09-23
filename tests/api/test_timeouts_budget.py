import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "api_timeout, request_timeout",
    [(2, 4)],
)
def test_api_timeout_budget(monkeypatch, api_timeout, request_timeout):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("CONTRACTAI_API_TIMEOUT_S", str(api_timeout))
    monkeypatch.setenv("CONTRACTAI_REQUEST_TIMEOUT_S", str(request_timeout))

    from contract_review_app.api import limits as limits_module

    importlib.reload(limits_module)
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)

    client = TestClient(
        app_module.app,
        headers={
            "x-schema-version": app_module.SCHEMA_VERSION,
            "x-api-key": "test-key",
        },
    )

    captured: dict[str, float] = {}

    async def fake_wait_for(awaitable, timeout, **_):
        captured["timeout"] = timeout
        raise asyncio.TimeoutError

    monkeypatch.setattr(app_module.asyncio, "wait_for", fake_wait_for)

    response = client.post(
        "/api/analyze",
        json={"text": "slow"},
    )

    assert response.status_code == 504
    payload = response.json()
    assert payload.get("status_text") == "timeout"
    assert payload.get("reason") == "analyze_timeout"
    assert captured["timeout"] == pytest.approx(limits_module.API_TIMEOUT_S)
    assert limits_module.API_TIMEOUT_S < limits_module.REQUEST_TIMEOUT_S
