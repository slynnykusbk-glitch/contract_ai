import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_suggest_in_accepts_clause_type_xor_and_normalizes_range():
    body = {
        "text": "Payment shall be made within 30 days.",
        "clause_type": "payment_terms",
        "mode": "friendly",
        "top_k": 3
    }
    r = client.post("/api/suggest_edits", data=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("suggestions", []), list)
    if j["suggestions"]:
        s0 = j["suggestions"][0]
        assert "range" in s0 and "start" in s0["range"] and "length" in s0["range"]

def test_suggest_in_legacy_clause_id_still_works():
    body = {
        "text": "Indemnity shall be limited.",
        "clause_id": "indemnity-1",
        "mode": "strict",
        "top_k": 1
    }
    r = client.post("/api/suggest_edits", data=json.dumps(body))
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_qa_recheck_accepts_span_and_range():
    text = "Hello world!"
    # range
    r1 = client.post("/api/qa-recheck", data=json.dumps({
        "text": text,
        "applied_changes": [{"range": {"start": 6, "length": 5}, "replacement": "LAW"}]
    }))
    assert r1.status_code == 200 and r1.json().get("status") == "ok"
    # span with end
    r2 = client.post("/api/qa-recheck", data=json.dumps({
        "text": text,
        "applied_changes": [{"span": {"start": 6, "end": 11}, "text": "LAW"}]
    }))
    assert r2.status_code == 200 and r2.json().get("status") == "ok"

def test_analyze_cache_idempotency_headers():
    body = {"text": "hello"}
    r1 = client.post("/api/analyze", data=json.dumps(body))
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") in ("miss", "MISS")
    r2 = client.post("/api/analyze", data=json.dumps(body))
    assert r2.status_code == 200
    assert r2.headers.get("x-cache").lower() == "hit"
    assert r1.headers.get("x-schema-version") == r2.headers.get("x-schema-version") == "1.0"
