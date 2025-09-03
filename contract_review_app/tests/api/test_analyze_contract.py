import pytest
import httpx
from contract_review_app.api.app import app
from contract_review_app.core.schemas import SCHEMA_VERSION


@pytest.mark.asyncio
async def test_analyze_ok_contract():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", trust_env=False
    ) as ac:
        body = {
            "text": "Governing law: England and Wales. Force majeure applies.",
            "mode": "live",
        }
        r = await ac.post("/api/analyze", json=body)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "ok"
        assert j["analysis"]["status"] == "ok"
        assert j["x_schema_version"] in ("1.3", SCHEMA_VERSION)
        assert r.headers.get("x-schema-version") == j["x_schema_version"]
