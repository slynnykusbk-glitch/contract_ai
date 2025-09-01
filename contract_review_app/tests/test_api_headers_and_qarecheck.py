import json
import hashlib
from fastapi.testclient import TestClient
from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def test_health_has_status_schema_and_header():
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    assert j.get("schema") == SCHEMA_VERSION
    assert isinstance(j.get("rules_count"), int)
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION

def test_trace_has_headers_and_shape():
    r = client.get("/api/trace/some-cid")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["cid"] == "some-cid"
    assert isinstance(j["events"], list)
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION
    assert r.headers.get("x-cache") == "miss"
    expected_cid = hashlib.sha256("/api/trace/some-cid".encode()).hexdigest()
    assert r.headers.get("x-cid") == expected_cid

def test_trace_index_has_headers_and_shape():
    r = client.get("/api/trace")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "cids" in j and isinstance(j["cids"], list)
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION
    assert r.headers.get("x-cache") == "miss"
    hdr_cid = r.headers.get("x-cid")
    assert hdr_cid and len(hdr_cid) == 64

def test_qarecheck_always_enveloped_status_ok_and_flattened():
    body = {"text": "Hello world", "applied_changes": [{"range": {"start": 6, "length": 5}, "text": "LEGAL"}]}
    r = client.post("/api/qa-recheck", content=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    for k in ("score_delta", "risk_delta", "status_from", "status_to", "residual_risks", "issues"):
        assert k in j
