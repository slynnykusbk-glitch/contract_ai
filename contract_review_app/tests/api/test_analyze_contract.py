import pytest
from httpx import AsyncClient
from contract_review_app.api.app import app
from contract_review_app.core.schemas import SCHEMA_VERSION


@pytest.mark.asyncio
async def test_analyze_ok_contract():
    async with AsyncClient(app=app, base_url="https://test", trust_env=False) as ac:
        r = await ac.post(
            "/api/analyze",
            json={
                "text": "Governing law: England and Wales. Force majeure applies.",
                "mode": "live",
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "ok"
        assert j["analysis"]["status"] == "ok"
        assert j["x_schema_version"] == SCHEMA_VERSION
        assert r.headers.get("x-schema-version") == SCHEMA_VERSION
