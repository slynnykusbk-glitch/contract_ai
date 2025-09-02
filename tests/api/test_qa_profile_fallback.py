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
    os.environ["AI_PROVIDER"] = "mock"
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


def test_qa_profile_fallback_to_vanilla(client):
    cid = "cid-fallback"
    resp = client.post(
        "/api/qa-recheck",
        json={"text": "hello", "profile": "smart"},
        headers={"x-cid": cid},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["profile"] == "vanilla"


def test_qa_empty_snapshot_defaults_vanilla(client):
    resp = client.post("/api/qa-recheck", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.json()["meta"]["profile"] == "vanilla"
