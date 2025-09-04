# contract_review_app/tests/api/test_app_contract.py
from __future__ import annotations

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


def test_health_shape():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "OK"
    assert data.get("schema") == SCHEMA_VERSION
    assert isinstance(data.get("rules_count"), int)
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION


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
    assert env["status"].upper() == "OK"
    assert "analysis" in env
    assert env["schema_version"] == SCHEMA_VERSION


def test_suggest_edits_returns_proposed_text():
    payload = {"text": "Lorem ipsum dolor sit amet."}
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    assert isinstance(out.get("proposed_text"), str)
    assert out["meta"]["provider"]


def test_qa_recheck_fallback_payload_and_deltas():
    text = "Payment shall be made within 30 days."
    # apply a trivial patch (replace '30' -> '60')
    patch = {"range": {"start": text.find("30"), "length": 2}, "replacement": "60"}
    r = client.post("/api/qa-recheck", json={"text": text, "applied_changes": [patch]})
    assert r.status_code == 200
    data: Dict[str, Any] = r.json()
    assert data["status"] == "ok"
    # shape guarantees
    for k in (
        "risk_delta",
        "score_delta",
        "status_from",
        "status_to",
        "residual_risks",
        "deltas",
    ):
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
    assert isinstance(payload.get("events"), list)


def test_panel_static_and_cache_headers():
    # version endpoint exists
    v = client.get("/panel/version.json")
    assert v.status_code == 200
    assert "schema_version" in v.json()

    # any static file (taskpane.html is in repo)
    page = client.get("/panel/taskpane.html")
    assert page.status_code == 200
    # no-store headers are set by the sub-app middleware
    cache_ctl = page.headers.get("Cache-Control")
    assert cache_ctl in {
        "no-store, must-revalidate",
        "no-store, no-cache, must-revalidate",
    }
    pragma = page.headers.get("Pragma")
    assert pragma in {None, "no-cache"}
    expires = page.headers.get("Expires")
    assert expires in {None, "0"}


def test_learning_endpoints_minimal_ok():
    log = client.post("/api/learning/log", json={"foo": "bar"})
    assert log.status_code == 204
    assert log.content == b""

    upd = client.post("/api/learning/update", json={"force": True})
    assert upd.status_code == 200
    assert upd.json()["updated"] is True
