import asyncio
import importlib
import time

import pytest
from fastapi import Request
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

    app = app_module.app
    limits = limits_module
    client = TestClient(
        app,
        headers={
            "x-schema-version": app_module.SCHEMA_VERSION,
            "x-api-key": "test-key",
        },
    )

    route_index = None
    for idx, r in enumerate(app.routes):
        methods = getattr(r, "methods", set())
        if getattr(r, "path", None) == "/api/analyze" and "POST" in methods:
            route_index = idx
            route = r
            break

    assert route_index is not None, "route /api/analyze not found"

    original_route = route
    app.router.routes.pop(route_index)

    async def slow_handler(request: Request):
        await asyncio.sleep(limits.API_TIMEOUT_S + 0.5)
        return app_module.JSONResponse({"status": "ok"})

    app.router.add_api_route("/api/analyze", slow_handler, methods=["POST"])

    try:
        start = time.perf_counter()
        response = client.post(
            "/api/analyze",
            json={"text": "slow"},
        )
        duration = time.perf_counter() - start
    finally:
        app.router.routes.pop()
        app.router.routes.insert(route_index, original_route)

    assert response.status_code == 504
    payload = response.json()
    assert payload.get("type") == "timeout"
    assert duration >= max(0.0, limits.API_TIMEOUT_S - 0.25)
    assert duration < limits.REQUEST_TIMEOUT_S
