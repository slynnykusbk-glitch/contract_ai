from fastapi.testclient import TestClient
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def _headers():
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    r2 = client.get("/api/health")
    assert r2.status_code == 200


def test_llm_ping_ok():
    r = client.get("/api/llm/ping")
    assert r.status_code == 200
    r2 = client.get("/llm/ping")
    assert r2.status_code == 200


def test_analyze_ok():
    payload = {"text": "Hello world"}
    r = client.post("/api/analyze", json=payload, headers=_headers())
    assert r.status_code == 200
    r2 = client.post("/analyze", json=payload, headers=_headers())
    assert r2.status_code == 200


def test_suggest_ok():
    payload = {"text": "Hello world"}
    r = client.post("/api/suggest_edits", json=payload, headers=_headers())
    assert r.status_code == 200
    r2 = client.post("/suggest_edits", json=payload, headers=_headers())
    assert r2.status_code == 200


def test_gpt_draft_ok():
    r_an = client.post("/api/analyze", json={"text": "Hi"}, headers=_headers())
    cid = r_an.headers.get("x-cid")
    payload = {"clause_id": cid, "text": "Draft confidentiality clause"}
    r = client.post("/api/gpt-draft", json=payload, headers=_headers())
    assert r.status_code == 200
    r_alias = client.post("/api/draft", json=payload, headers=_headers())
    assert r_alias.status_code == 200
    for p in ["/api/gpt/draft", "/gpt-draft", "/api/gpt_draft"]:
        assert client.post(p, json=payload, headers=_headers()).status_code == 404


def test_supports_ok():
    assert client.get("/api/supports").status_code == 200
