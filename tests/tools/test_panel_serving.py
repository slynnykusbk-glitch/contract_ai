import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from contract_review_app.api.app import app, PANEL_DIR


def _fs_size(rel: str) -> int:
    return os.stat(PANEL_DIR / rel).st_size


def test_head_and_get_html_js():
    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            for rel in ["taskpane.html", "taskpane.bundle.js"]:
                head = await ac.head(f"/panel/{rel}")
                assert head.status_code == 200
                assert int(head.headers["content-length"]) == _fs_size(rel)
                get = await ac.get(f"/panel/{rel}")
                assert get.status_code == 200
                assert len(get.content) == _fs_size(rel)

    asyncio.run(_run())


def test_parallel_head_get():
    def do_head():
        with TestClient(app) as c:
            r = c.head("/panel/taskpane.html")
            assert r.status_code == 200

    def do_get():
        with TestClient(app) as c:
            r = c.get("/panel/taskpane.html")
            assert r.status_code == 200

    with ThreadPoolExecutor() as tp:
        h = tp.submit(do_head)
        g = tp.submit(do_get)
        h.result()
        g.result()
