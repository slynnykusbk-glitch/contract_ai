from fastapi.testclient import TestClient

from contract_review_app.api.app import app
import contract_review_app.api.explain as explain_mod

client = TestClient(app)


def test_explain_privacy(monkeypatch):
    monkeypatch.setenv("FEATURE_LLM_EXPLAIN", "1")

    def echo_tokens(messages, **kwargs):
        return {"content": "<EMAIL_0> <PHONE_0> <NI_0>", "usage": {}}

    monkeypatch.setattr(explain_mod.LLM_PROVIDER, "chat", echo_tokens)
    text = "Contact john@example.com or 123-456-7890 NI AB123456C"
    req = {
        "finding": {
            "code": "uk_ucta_2_1_invalid",
            "message": "Exclusion of liability",
            "span": {"start": 0, "end": 10},
        },
        "text": text,
    }
    resp = client.post("/api/explain", json=req)
    data = resp.json()
    assert "john@example.com" not in data["reasoning"]
    assert "123-456-7890" not in data["reasoning"]
    assert "AB123456C" not in data["reasoning"]
