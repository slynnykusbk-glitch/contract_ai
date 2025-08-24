# contract_review_app/tests/api/test_api_smoke.py
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_api_analyze_smoke(monkeypatch):
    # Стаб аналізатора
    def _fake_analyze(text: str):
        return {"status": "OK", "findings": [], "summary": {"len": len(text)}}

    import contract_review_app.api.app as app_mod
    monkeypatch.setattr(app_mod, "_analyze_document", _fake_analyze, raising=True)

    resp = client.post("/api/analyze", json={"text": "Hello", "language": "en"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert data["summary"]["len"] == 5


def test_api_gpt_draft_new_request(monkeypatch):
    def _fake_draft(inp):
        return {"text": "DRAFT", "model": "mock"}

    import contract_review_app.api.app as app_mod
    monkeypatch.setattr(app_mod, "run_gpt_draft", _fake_draft, raising=True)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    new_req = {"analysis": {"status": "OK"}, "model": "gpt-4"}
    resp = client.post("/api/gpt/draft", json=new_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_text"] == "DRAFT"
    assert data["status"] == "ok"
    assert data["meta"]["model"] == "mock"


def test_api_gpt_draft_legacy_request(monkeypatch):
    def _fake_draft(inp):
        return {"text": "[AI-DRAFT] Text", "model": "mock"}

    import contract_review_app.api.app as app_mod
    monkeypatch.setattr(app_mod, "run_gpt_draft", _fake_draft, raising=True)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    legacy_req = {"clause_type": "termination", "text": "Text", "language": "en"}
    resp = client.post("/api/gpt/draft", json=legacy_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_text"].startswith("[AI-DRAFT]")
    assert data["status"] == "ok"
    assert data["meta"]["model"] == "mock"
