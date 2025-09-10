import pytest
import httpx
from contract_review_app.api.app import app


@pytest.mark.asyncio
async def test_qa_recheck_no_500():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", trust_env=False
    ) as ac:
        body = {
            "text": "Clause text",
            "rules": [{"id": "R1", "status": "warn", "note": "check wording"}],
        }
        r = await ac.post("/api/qa-recheck", json=body)
        assert r.status_code in (200, 400, 422)  # но не 500
