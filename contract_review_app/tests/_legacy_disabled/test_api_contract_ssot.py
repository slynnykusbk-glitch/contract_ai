import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def test_suggest_edits_accepts_text():
    body = {"text": "Payment shall be made within 30 days."}
    r = client.post("/api/suggest_edits", content=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("proposed_text"), str)


def test_suggest_edits_with_clause_id_still_ok():
    body = {"text": "Indemnity shall be limited.", "clause_id": "indemnity-1"}
    r = client.post("/api/suggest_edits", content=json.dumps(body))
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_qa_recheck_accepts_span_and_range():
    text = "Hello world!"
    # range
    r1 = client.post(
        "/api/qa-recheck",
        content=json.dumps(
            {
                "text": text,
                "applied_changes": [
                    {"range": {"start": 6, "length": 5}, "replacement": "LAW"}
                ],
            }
        ),
    )
    assert r1.status_code == 200 and r1.json().get("status") == "ok"
    # span with end
    r2 = client.post(
        "/api/qa-recheck",
        content=json.dumps(
            {
                "text": text,
                "applied_changes": [{"span": {"start": 6, "end": 11}, "text": "LAW"}],
            }
        ),
    )
    assert r2.status_code == 200 and r2.json().get("status") == "ok"


def test_analyze_cache_idempotency_headers():
    body = {"text": "hello"}
    r1 = client.post("/api/analyze", content=json.dumps(body))
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") in ("miss", "MISS")
    r2 = client.post("/api/analyze", content=json.dumps(body))
    assert r2.status_code == 200
    assert r2.headers.get("x-cache").lower() == "hit"
    assert (
        r1.headers.get("x-schema-version")
        == r2.headers.get("x-schema-version")
        == SCHEMA_VERSION
    )
