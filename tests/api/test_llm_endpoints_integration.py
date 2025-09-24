import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient


def _reload_app():
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    os.environ["LLM_PROVIDER"] = "mock"
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


def test_endpoints_ok(client):
    r = client.post("/api/analyze", json={"text": "hi"})
    cid = r.headers.get("x-cid")
    assert (
        client.post("/api/gpt-draft", json={"clause_id": cid, "text": "hi"}).status_code
        == 200
    )
    assert client.post("/api/suggest_edits", json={"text": "hi"}).status_code == 200
    assert client.post("/api/qa-recheck", json={"text": "hi"}).status_code == 200
