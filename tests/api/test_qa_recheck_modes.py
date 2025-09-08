import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient


def _create_client(env: dict) -> tuple[TestClient, list[str]]:
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
        "contract_review_app.api.orchestrator",
        "contract_review_app.gpt.service",
        "contract_review_app.gpt.clients.mock_client",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    for k, v in env.items():
        os.environ[k] = v
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)
    client = TestClient(app_module.app)
    return client, modules


@pytest.fixture()
def client_mock():
    env = {"LLM_PROVIDER": "mock", "AZURE_KEY_INVALID": "1"}
    client, modules = _create_client(env)
    try:
        yield client
    finally:
        for m in modules:
            sys.modules.pop(m, None)
        for k in env:
            os.environ.pop(k, None)


def test_qa_recheck_mock_ok(client_mock):
    payload = {"text": "hello", "rules": {}}
    resp = client_mock.post("/api/qa-recheck", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_qa_recheck_azure_bad_key():
    env = {
        "LLM_PROVIDER": "azure",
        "AZURE_OPENAI_ENDPOINT": "https://example.com",
        "AZURE_OPENAI_API_VERSION": "2024-02-15",
        "AZURE_OPENAI_DEPLOYMENT": "gpt",
        "AZURE_OPENAI_KEY": "bad",
    }
    client, modules = _create_client(env)
    try:
        resp = client.post("/api/qa-recheck", json={"text": "hello", "rules": {}})
        assert resp.status_code == 401
        body = resp.json()
        assert body["status"] == "error"
        assert body.get("error_code") == "provider_auth"
    finally:
        for m in modules:
            sys.modules.pop(m, None)
        for k in env:
            os.environ.pop(k, None)
