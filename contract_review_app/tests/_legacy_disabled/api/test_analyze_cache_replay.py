import pytest
from httpx import AsyncClient, ASGITransport
from contract_review_app.api.app import app


@pytest.mark.asyncio
async def test_analyze_cache_and_replay():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        body = {
            "text": "Governing law: England and Wales. Force majeure applies.",
            "mode": "live",
        }
        r1 = await ac.post("/api/analyze", json=body)
        assert r1.status_code == 200
        j1 = r1.json()
        cid = r1.headers.get("x-cid")
        h = r1.headers.get("x-doc-hash")
        assert cid and h
        assert r1.headers.get("x-cache") in ("miss", "hit")

        r2 = await ac.post("/api/analyze", json=body)
        assert r2.status_code == 200
        assert r2.headers.get("x-cache") == "hit"
        assert r2.headers.get("x-doc-hash") == h
        assert r2.json() == j1

        r3 = await ac.get(f"/api/analyze/replay?cid={cid}")
        assert r3.status_code == 200
        assert r3.headers.get("x-cache") == "replay"
        assert r3.json() == j1

        r4 = await ac.get(f"/api/analyze/replay?hash={h}")
        assert r4.status_code == 200
        assert r4.json() == j1
