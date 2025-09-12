import asyncio
import logging
from httpx import AsyncClient, ASGITransport
from contract_review_app.api.app import app


async def _head_get(ac: AsyncClient, path: str):
    head = await ac.head(path)
    get = await ac.get(path)
    assert head.status_code == 200
    assert get.status_code == 200
    assert int(head.headers["content-length"]) == len(get.content) > 0


def test_head_and_get_html_js():
    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await _head_get(ac, "/panel/taskpane.html")
            await _head_get(ac, "/panel/taskpane.bundle.js")
    asyncio.run(_run())


def test_parallel_gets():
    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r1, r2 = await asyncio.gather(
                ac.get("/panel/taskpane.html"),
                ac.get("/panel/taskpane.html"),
            )
            assert r1.status_code == r2.status_code == 200
            assert len(r1.content) == len(r2.content) > 0
    asyncio.run(_run())


def test_no_errors_after_head_get(caplog):
    async def _run():
        caplog.set_level(logging.ERROR)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.head("/panel/taskpane.html")
            await ac.get("/panel/taskpane.html")
        assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)
    asyncio.run(_run())
