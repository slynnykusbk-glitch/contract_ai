import os
import sys
import importlib

import pytest
from fastapi.testclient import TestClient


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


def test_summary_post_by_cid_ok(client):
    r_analyze = client.post("/api/analyze", json={"text": "hello world"})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    r_post = client.post("/api/summary", json={"cid": cid})
    assert r_post.status_code == 200
    assert r_post.json().get("summary")


def test_summary_post_bad_body(client):
    r = client.post("/api/summary", json={})
    assert r.status_code == 422
    detail = r.json().get("detail")
    msg = (
        "".join(d.get("msg", "") for d in detail)
        if isinstance(detail, list)
        else str(detail)
    )
    assert "cid" in msg and "hash" in msg


def test_summary_post_both_fields(client):
    r = client.post("/api/summary", json={"cid": "a", "hash": "b"})
    assert r.status_code == 422
    detail = r.json().get("detail")
    msg = (
        "".join(d.get("msg", "") for d in detail)
        if isinstance(detail, list)
        else str(detail)
    )
    assert "one" in msg.lower() or "only" in msg.lower()
