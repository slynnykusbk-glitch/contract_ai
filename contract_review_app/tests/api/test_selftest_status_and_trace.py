import pytest
import httpx
import json

from contract_review_app.api.app import app


@pytest.mark.asyncio
async def test_health_status_ok_lowercase():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_analyze_status_and_trace_snapshot():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        body = {"text": "Governing law: England and Wales. Force majeure applies.", "mode": "live"}
        r = await ac.post(
            "/api/analyze",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200
        j = r.json()
        assert j.get("status") == "ok"
        assert j.get("analysis", {}).get("status") == "ok"
        cid = r.headers.get("x-cid")
        assert cid and len(cid) >= 32
        t = await ac.get(f"/api/trace/{cid}")
        assert t.status_code == 200
        tj = t.json()
        assert tj.get("path") == "/api/analyze"
        assert "body" in tj and "headers" in tj
