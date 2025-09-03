import re

from fastapi.testclient import TestClient

import pytest

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


@pytest.mark.parametrize("path", ["/api/analyze", "/api/gpt-draft"])
def test_std_headers_present_and_valid(path):
    payload1 = {"text": "hello"}
    payload2 = {"text": "world"}
    r1 = client.post(path, json=payload1)
    r2 = client.post(path, json=payload1)
    r3 = client.post(path, json=payload2)
    assert r1.headers["x-cid"] == r2.headers["x-cid"]
    assert r1.headers["x-cid"] != r3.headers["x-cid"]
    assert r1.headers["x-schema-version"] == SCHEMA_VERSION
    assert int(r1.headers["x-latency-ms"]) >= 0
    assert re.fullmatch(r"[0-9a-f]{64}", r1.headers["x-cid"])


def test_error_handlers_also_emit_headers():
    r = client.post("/api/analyze", json={})
    assert r.status_code == 422
    for h in ("x-schema-version", "x-latency-ms", "x-cid"):
        assert h in r.headers


def test_trace_uses_same_cid_and_latency(monkeypatch):
    last = {}

    def fake_push(cid, event):
        last.clear()
        last.update(event)
        last["cid"] = cid

    monkeypatch.setattr("contract_review_app.api.app._trace_push", fake_push)

    payload = {"text": "stable"}
    resp = client.post("/api/analyze", json=payload)

    assert last["cid"] == resp.headers["x-cid"]
    event_ms = last["ms"]
    header_ms = int(resp.headers["x-latency-ms"])
    assert event_ms == header_ms or abs(event_ms - header_ms) <= 5
