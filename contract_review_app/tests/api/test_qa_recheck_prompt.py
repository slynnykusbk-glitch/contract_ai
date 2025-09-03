import pytest
from httpx import AsyncClient
from contract_review_app.api.app import app


@pytest.mark.asyncio
async def test_qa_recheck_no_500():
    async with AsyncClient(app=app, base_url="https://test", trust_env=False) as ac:
        body = {"text": "Clause text", "rules": [{"id": "R1", "status": "warn", "note": "check"}]}
        r = await ac.post("/api/qa-recheck", json=body)
        assert r.status_code in (200, 400, 422)
