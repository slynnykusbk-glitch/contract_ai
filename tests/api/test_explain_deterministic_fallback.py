import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_explain_deterministic(monkeypatch):
    monkeypatch.setenv("FEATURE_LLM_EXPLAIN", "0")
    req = {
        "finding": {
            "code": "uk_ucta_2_1_invalid",
            "message": "Exclusion of liability for personal injury",
            "span": {"start": 0, "end": 10},
        },
        "text": "Exclusion of liability for personal injury is void.",
    }
    resp = client.post("/api/explain", json=req)
    data = resp.json()
    assert "Legal basis:" in data["reasoning"]
    assert "UCTA" in data["reasoning"]
