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
    # Навіть якщо новий формат не потребує аналізу, підкинемо стаб
    def _fake_analyze(text: str):
        return {"status": "OK", "findings": []}

    # Стаб GPT-пайплайна: приймає GPTDraftRequest
    def _fake_gpt_pipeline(gpt_req):
        assert "status" in gpt_req.analysis  # перевірка що analysis передано
        return {
            "clause_type": "confidentiality",
            "original_text": "ORIG",
            "draft_text": "DRAFT",
            "explanation": "ok",
            "score": 90,
            "status": "ok",
            "title": "Confidentiality - Draft",
        }

    import contract_review_app.api.app as app_mod
    monkeypatch.setattr(app_mod, "_analyze_document", _fake_analyze, raising=True)
    monkeypatch.setattr(app_mod, "run_gpt_drafting_pipeline", _fake_gpt_pipeline, raising=True)

    # Новий формат: передаємо одразу analysis
    new_req = {
        "analysis": {"status": "OK", "findings": [], "summary": {"x": 1}},
        "model": "gpt-4",
    }
    resp = client.post("/api/gpt/draft", json=new_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_text"] == "DRAFT"
    assert data["status"] == "ok"
    assert data["score"] == 90


def test_api_gpt_draft_legacy_request(monkeypatch):
    # Стаб аналізатора для легасі-шляху
    def _fake_analyze(text: str):
        assert text == "Text"
        return {"status": "OK", "findings": [{"code": "X"}]}

    # Стаб GPT-пайплайна
    def _fake_gpt_pipeline(gpt_req):
        # очікуємо, що analysis вже підставлений з _fake_analyze
        assert gpt_req.analysis["status"] == "OK"
        return {
            "clause_type": "termination",
            "original_text": "Text",
            "draft_text": "[AI-DRAFT] Text",
            "explanation": "ok",
            "score": 85,
            "status": "ok",
            "title": "Termination - Draft",
        }

    import contract_review_app.api.app as app_mod
    monkeypatch.setattr(app_mod, "_analyze_document", _fake_analyze, raising=True)
    monkeypatch.setattr(app_mod, "run_gpt_drafting_pipeline", _fake_gpt_pipeline, raising=True)

    legacy_req = {"clause_type": "termination", "text": "Text", "language": "en"}
    resp = client.post("/api/gpt/draft", json=legacy_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_text"].startswith("[AI-DRAFT]")
    assert data["status"] == "ok"
    assert data["score"] == 85
