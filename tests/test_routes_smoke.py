from fastapi.testclient import TestClient
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
    r_an = client.post("/api/analyze", json={"text": "Hi"})
    cid = r_an.headers.get("x-cid")
    payload = {"cid": cid, "clause": "Draft confidentiality clause"}
    r = client.post("/api/gpt-draft", json=payload)
    assert r.status_code == 200
    for p in ["/api/gpt/draft", "/gpt-draft", "/api/gpt_draft"]:
        assert client.post(p, json=payload).status_code == 404
