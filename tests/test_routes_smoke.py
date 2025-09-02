from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


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
    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 200
    r2 = client.post("/analyze", json=payload)
    assert r2.status_code == 200


def test_suggest_ok():
    payload = {"text": "Hello world"}
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 200
    r2 = client.post("/suggest_edits", json=payload)
    assert r2.status_code == 200


def test_gpt_draft_ok():
    payload = {"prompt": "Draft confidentiality clause"}
    r = client.post("/api/gpt-draft", json=payload)
    assert r.status_code == 200
    r2 = client.post("/gpt-draft", json=payload)
    assert r2.status_code == 200
    r3 = client.post("/api/gpt_draft", json=payload)  # underscore alias
    assert r3.status_code == 200
