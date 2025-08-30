import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("schema") == SCHEMA_VERSION
    assert isinstance(data.get("rules_count"), int)
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION

def test_analyze_envelope_and_keys():
    r = client.post("/api/analyze", content=json.dumps({"text": "Some clause text."}))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "OK"
    # legacy-compatible keys
    for k in ("analysis", "results", "clauses", "document"):
        assert k in j


def test_suggest_edits_smoke():
    r = client.post("/api/suggest_edits", content=json.dumps({
        "text": "Termination by convenience.",
        "clause_type": "termination",
        "mode": "friendly",
        "top_k": 1
    }))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    # normalized range
    if j.get("edits"):
        rng = j["edits"][0].get("range", {})
        assert {"start", "length"}.issubset(rng.keys())

def test_qa_recheck_smoke_flattened():
    r = client.post("/api/qa-recheck", content=json.dumps({
        "text": "Confidential info shall be protected.",
        "applied_changes": [{"range": {"start": 0, "length": 12}, "text": "Sensitive data"}]
    }))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    for k in ("score_delta", "risk_delta", "status_from", "status_to", "residual_risks"):
        assert k in j

def test_trace_smoke():
    r = client.get("/api/trace/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("events", []), list)
