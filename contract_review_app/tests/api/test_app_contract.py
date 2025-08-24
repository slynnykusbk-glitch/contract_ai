# contract_review_app/tests/api/test_app_contract.py
from __future__ import annotations

import json
from typing import Dict, Any

from fastapi.testclient import TestClient

from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def _is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except Exception:
        return False


def test_health_headers_and_shape():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["schema_version"] == SCHEMA_VERSION
    assert isinstance(data.get("rules_count"), int)

    # std headers must exist
    assert r.headers.get("x-cid") == "health"
    assert r.headers.get("x-cache") == "miss"
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION
    assert _is_int(r.headers.get("x-latency-ms", "0"))


def test_analyze_idempotent_cache_hit_on_second_call():
    payload = {"text": "Confidentiality clause example."}
    r1 = client.post("/api/analyze", json=payload)
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "miss"

    r2 = client.post("/api/analyze", json=payload)
    assert r2.status_code == 200
    assert r2.headers.get("x-cache") == "hit"

    env = r2.json()
    # envelope shape
    assert env["status"] == "ok"
    assert "analysis" in env and "results" in env and "document" in env
    assert env["schema_version"] == SCHEMA_VERSION


def test_suggest_edits_normalization_and_bounds():
    # With no orchestrator/pipeline this uses rule-based fallback
    payload = {
        "text": "Lorem ipsum dolor sit amet.",
        "clause_id": "C-1",
        "mode": "friendly",
        "top_k": 7,  # should be clamped 1..10 by app layer
    }
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    suggestions = out.get("suggestions") or []
    assert isinstance(suggestions, list) and len(suggestions) >= 1

    for s in suggestions:
        # robust normalized range
        assert isinstance(s.get("range"), dict)
        assert "start" in s["range"] and "length" in s["range"]
        assert isinstance(s["range"]["start"], int)
        assert isinstance(s["range"]["length"], int)
        # message is always present after normalization
        assert isinstance(s.get("message", ""), str)


def test_gpt_draft_shape_and_headers():
    r = client.post("/api/gpt/draft", json={"text": "Some clause text", "mode": "friendly"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "draft_text" in body
    assert isinstance(body.get("meta", {}), dict)
    # std headers
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION
    assert _is_int(r.headers.get("x-latency-ms", "0"))


def test_qa_recheck_fallback_payload_and_deltas():
    text = "Payment shall be made within 30 days."
    # apply a trivial patch (replace '30' -> '60')
    patch = {"range": {"start": text.find("30"), "length": 2}, "replacement": "60"}
    r = client.post("/api/qa-recheck", json={"text": text, "applied_changes": [patch]})
    assert r.status_code == 200
    data: Dict[str, Any] = r.json()
    assert data["status"] == "ok"
    # shape guarantees
    for k in ("risk_delta", "score_delta", "status_from", "status_to", "residual_risks", "deltas"):
        assert k in data
    assert isinstance(data["deltas"], dict)


def test_trace_middleware_records_events():
    # produce at least one event
    client.get("/health")
    tr = client.get("/api/trace/health")
    assert tr.status_code == 200
    payload = tr.json()
    assert payload["status"] == "ok"
    assert payload["cid"] == "health"
    # there should be at least one recorded event for /health
    assert isinstance(payload.get("events"), list)
    assert len(payload["events"]) >= 1
    # sanity on a single event keys
    ev = payload["events"][-1]
    for k in ("ts", "method", "path", "status", "ms"):
        assert k in ev


def test_panel_static_and_cache_headers():
    # version endpoint exists
    v = client.get("/panel/version.json")
    assert v.status_code == 200
    assert "schema_version" in v.json()

    # any static file (taskpane.html is in repo)
    page = client.get("/panel/taskpane.html")
    assert page.status_code == 200
    # no-store headers are set by the sub-app middleware
    assert page.headers.get("Cache-Control") == "no-store, must-revalidate"
    assert page.headers.get("Pragma") == "no-cache"
    assert page.headers.get("Expires") == "0"


def test_learning_endpoints_minimal_ok():
    log = client.post("/api/learning/log", json={"any": "json"})
    assert log.status_code == 204

    upd = client.post("/api/learning/update", json={"force": True})
    assert upd.status_code == 200
    assert upd.json()["updated"] is True
