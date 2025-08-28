import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[3]))


def test_routes_absent_by_default():
    os.environ.pop("CONTRACTAI_LLM_API", None)
    from contract_review_app.api import app as app_mod

    client = TestClient(app_mod.app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    r2 = client.post("/api/gpt/draft", json={})
    assert r2.status_code == 404


def build_client() -> TestClient:
    os.environ["CONTRACTAI_LLM_API"] = "1"
    mod = importlib.import_module("contract_review_app.api.app")
    importlib.reload(mod)
    return TestClient(mod.app)


def test_routes_enabled(monkeypatch):
    client = build_client()
    body = {
        "question": "What is the term?",
        "context_text": "The term is five years.",
        "citations": [
            {
                "instrument": "NDA",
                "section": "5",
                "system": "us",
                "url": "https://example.com/nda#5",
            }
        ],
    }
    resp = client.post("/api/gpt/draft", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "mock"
    assert data["model"] == "mock-legal-v1"
    assert data["verification_status"] in {
        "verified",
        "partially_verified",
        "unverified",
        "failed",
    }
    assert "<<EVIDENCE>>" in data["prompt"]
    assert "NDA §5" in data["prompt"]

    resp2 = client.post("/api/gpt/suggest_edits", json=body)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["provider"] == "mock"
    assert data2["model"] == "mock-legal-v1"
    assert data2["verification_status"] in {
        "verified",
        "partially_verified",
        "unverified",
        "failed",
    }
    assert "<<EVIDENCE>>" in data2["prompt"]
    assert "NDA §5" in data2["prompt"]
