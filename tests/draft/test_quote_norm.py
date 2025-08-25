from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from contract_review_app.api.app import app
import contract_review_app.api.app as app_mod

client = TestClient(app)


def test_rulebased_fallback_normalizes_quotes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(app_mod, "run_gpt_draft", None, raising=False)
    monkeypatch.setattr(app_mod, "run_analyze", None, raising=False)

    class DummyPipeline:
        async def synthesize_draft(self, doc, mode):
            return {"text": "Here’s a “smart” clause"}

    monkeypatch.setattr(app_mod, "pipeline", DummyPipeline(), raising=True)

    resp = client.post("/api/gpt/draft", json={"analysis": {"text": ""}, "model": "gpt-4"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["model"] == "rulebased"
    assert "’" not in data["draft_text"]
    assert "“" not in data["draft_text"]
    assert "”" not in data["draft_text"]
