import asyncio

from fastapi.testclient import TestClient

from contract_review_app.api.app import app


def test_analyze_timeout_returns_problem_json(monkeypatch):
    client = TestClient(app)

    async def _raise_timeout(awaitable, timeout=None):
        try:
            awaitable.close()
        except AttributeError:
            pass
        raise asyncio.TimeoutError

    monkeypatch.setattr("contract_review_app.api.app.asyncio.wait_for", _raise_timeout)

    headers = {
        "x-api-key": "dummy",
        "x-schema-version": "1.4",
    }

    response = client.post("/api/analyze", json={"text": "hello"}, headers=headers)

    assert response.status_code == 504
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "status": 504,
        "status_text": "timeout",
        "reason": "analyze_timeout",
    }
    assert response.headers.get("x-cid")
    assert response.headers.get("X-Cid") == response.headers.get("x-cid")
