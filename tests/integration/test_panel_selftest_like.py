import importlib
import os
import sys
from fastapi.testclient import TestClient


def _build_client():
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    os.environ["LLM_PROVIDER"] = "mock"
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)

    def fake_analyze(text: str):
        return {
            "analysis": {"issues": ["dummy"]},
            "results": {},
            "clauses": [],
            "document": {"text": text},
        }

    app_module._analyze_document = fake_analyze
    client = TestClient(app_module.app)
    return client, modules


def test_panel_selftest_like():
    client, modules = _build_client()
    try:
        assert client.get("/api/llm/ping").status_code == 200
        r = client.post("/api/analyze", json={"text": "Hi"})
        assert r.status_code == 200
        cid = r.headers.get("x-cid")
        assert (
            client.post(
                "/api/gpt-draft", json={"clause_id": cid, "text": "Hi"}
            ).status_code
            == 200
        )
        assert (
            client.post("/api/qa-recheck", json={"text": "hi", "rules": {}}).status_code
            == 200
        )
        assert (
            client.post(
                "/api/qa-recheck", json={"text": "hi", "rules": [{"R1": "on"}]}
            ).status_code
            == 200
        )
        assert client.post("/api/suggest_edits", json={"text": "Hi"}).status_code == 200
        assert (
            client.post(
                "/api/citation/resolve",
                json={"citations": [{"instrument": "ACT", "section": "1"}]},
            ).status_code
            == 200
        )
        assert client.get("/api/trace").status_code == 200
        assert client.get(f"/api/report/{cid}.html").status_code == 200
    finally:
        for m in modules:
            sys.modules.pop(m, None)
        os.environ.pop("LLM_PROVIDER", None)
