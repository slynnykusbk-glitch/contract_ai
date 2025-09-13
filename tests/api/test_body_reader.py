import asyncio
import httpx
import pytest

import contract_review_app.api.app as api_mod


@pytest.mark.asyncio
async def test_streaming_body_reader_no_content_length(monkeypatch):
    monkeypatch.setattr(api_mod, "MAX_BODY_BYTES", 1024)

    chunk = b"x" * 600
    sent = 0

    async def gen():
        nonlocal sent
        for _ in range(100):
            sent += len(chunk)
            yield chunk
            await asyncio.sleep(0)

    transport = httpx.ASGITransport(app=api_mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/calloff/validate",
            content=gen(),
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert "content-length" not in response.request.headers
    assert sent <= api_mod.MAX_BODY_BYTES + len(chunk)
