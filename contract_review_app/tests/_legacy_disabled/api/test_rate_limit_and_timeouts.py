import asyncio

from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_timeout_returns_504(monkeypatch):
    monkeypatch.setattr("contract_review_app.api.app.API_TIMEOUT_S", 0.01)

    async def slow(text: str) -> dict:
        await asyncio.sleep(0.05)
        return {}

    monkeypatch.setattr("contract_review_app.api.app._analyze_document", slow)
    r = client.post("/api/analyze", json={"text": "hello"})
    assert r.status_code == 504
    data = r.json()
    assert data["type"] == "timeout"
    for h in ("x-schema-version", "x-latency-ms", "x-cid"):
        assert h in r.headers


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr("contract_review_app.api.app.API_RATE_LIMIT_PER_MIN", 2)
    monkeypatch.setattr("contract_review_app.api.app._RATE_BUCKETS", {})
    payload = {"text": "hi"}
    client.post("/api/analyze", json=payload)
    client.post("/api/analyze", json=payload)
    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 429
    data = r.json()
    assert data["type"] == "too_many_requests"
    assert "Retry-After" in r.headers
    for h in ("x-schema-version", "x-latency-ms", "x-cid"):
        assert h in r.headers
