from fastapi.testclient import TestClient

from contract_review_app.api.app import app
import contract_review_app.api.explain as explain_mod

client = TestClient(app)


REQ = {
    "finding": {
        "code": "uk_ucta_2_1_invalid",
        "message": "Exclusion of liability for personal injury",
        "span": {"start": 0, "end": 10},
    },
    "text": "Exclusion of liability for personal injury is void.",
}


def test_llm_verification(monkeypatch):
    monkeypatch.setenv("FEATURE_LLM_EXPLAIN", "1")

    def no_refs(messages, **kwargs):
        return {"content": "some explanation without refs", "usage": {}}

    monkeypatch.setattr(explain_mod.LLM_PROVIDER, "chat", no_refs)
    resp = client.post("/api/explain", json=REQ)
    data = resp.json()
    assert data["verification_status"] == "missing_citations"
    assert "Legal basis:" in data["reasoning"]  # fallback used

    def with_refs(messages, **kwargs):
        return {"content": "reason [c1]", "usage": {}}

    monkeypatch.setattr(explain_mod.LLM_PROVIDER, "chat", with_refs)
    resp2 = client.post("/api/explain", json=REQ)
    data2 = resp2.json()
    assert data2["verification_status"] == "ok"
    assert "reason" in data2["reasoning"]
