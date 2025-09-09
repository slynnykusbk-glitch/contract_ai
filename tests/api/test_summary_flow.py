import os
import sys
import importlib

import pytest
from fastapi.testclient import TestClient


# helper to create isolated client using mock LLM provider


def _create_client():
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
        "contract_review_app.api.orchestrator",
        "contract_review_app.gpt.service",
        "contract_review_app.gpt.clients.mock_client",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    os.environ.setdefault("LLM_PROVIDER", "mock")
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)
    from contract_review_app.api.models import SCHEMA_VERSION

    client = TestClient(app_module.app, headers={"x-schema-version": SCHEMA_VERSION})
    return client, modules


@pytest.fixture()
def client():
    client, modules = _create_client()
    try:
        yield client
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_summary_flow(client):
    r_analyze = client.post("/api/analyze", json={"text": "hello world"})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid

    r_post = client.post("/api/summary", json={"cid": cid})
    assert r_post.status_code == 200
    assert r_post.json().get("summary")

    r_get = client.get("/api/summary")
    assert r_get.status_code == 200
