import re

import os
import re
from fastapi.testclient import TestClient

import pytest

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
HEADERS = {"x-api-key": "k", "x-schema-version": SCHEMA_VERSION}


@pytest.mark.parametrize("path", ["/api/analyze", "/api/gpt-draft"])
def test_std_headers_present_and_valid(path):
    payload1 = {"text": "hello"}
    payload2 = {"text": "world"}
    r1 = client.post(path, json=payload1, headers=HEADERS.copy())
    r2 = client.post(path, json=payload1, headers=HEADERS.copy())
    r3 = client.post(path, json=payload2, headers=HEADERS.copy())
    assert r1.headers["x-schema-version"] == SCHEMA_VERSION
    assert re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}", r1.headers["x-cid"])
    if path == "/api/analyze":
        assert r1.headers["x-cid"] == r2.headers["x-cid"]
        assert r3.headers["x-cid"] != r1.headers["x-cid"]


def test_error_handlers_also_emit_headers():
    r = client.post("/api/analyze", json={}, headers=HEADERS.copy())
    assert r.status_code in (400, 422)
    for h in ("x-schema-version", "x-cid"):
        assert h in r.headers


def test_trace_uses_same_cid_and_latency(monkeypatch):
    last = {}

    def fake_push(cid, event):
        last.clear()
        last.update(event)
        last["cid"] = cid

    monkeypatch.setattr("contract_review_app.api.app._trace_push", fake_push)

    payload = {"text": "stable"}
    resp = client.post("/api/analyze", json=payload, headers=HEADERS.copy())

    assert last["cid"] == resp.headers["x-cid"]
