from fastapi.testclient import TestClient

from contract_review_app.api.app import app


client = TestClient(app)


def test_rule_fallback(monkeypatch):
    for k in [
        "OPENAI_API_KEY",
        "AZURE_OPENAI_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(k, raising=False)
    resp = client.post("/api/gpt/draft", json={"text": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft_text"] != ""
    assert data["meta"]["model"] == "rulebased"
