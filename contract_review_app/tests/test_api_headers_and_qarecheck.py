import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_health_has_headers_and_envelope():
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    assert r.headers.get("x-schema-version") == "1.0"
    assert r.headers.get("x-cache") == "miss"
    # x-cid may be present (e.g., "health") or omitted; both acceptable

def test_trace_has_headers_and_shape():
    r = client.get("/api/trace/some-cid")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["cid"] == "some-cid"
    assert isinstance(j["events"], list)
    assert r.headers.get("x-schema-version") == "1.0"
    assert r.headers.get("x-cache") == "miss"
    assert r.headers.get("x-cid") == "some-cid"

def test_trace_index_has_headers_and_shape():
    r = client.get("/api/trace")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "cids" in j and isinstance(j["cids"], list)
    assert r.headers.get("x-schema-version") == "1.0"
    assert r.headers.get("x-cache") == "miss"
    assert r.headers.get("x-cid") in (None, "trace-index", "")

def test_qarecheck_always_enveloped_status_ok_and_flattened():
    body = {"text": "Hello world", "applied_changes": [{"range": {"start": 6, "length": 5}, "text": "LEGAL"}]}
    r = client.post("/api/qa-recheck", data=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    for k in ("score_delta", "risk_delta", "status_from", "status_to", "residual_risks"):
        assert k in j
