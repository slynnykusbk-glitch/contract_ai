import importlib
import os
import sys

from fastapi.testclient import TestClient

from contract_review_app.api.models import SCHEMA_VERSION


def _create_client():
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
        "contract_review_app.api.orchestrator",
        "contract_review_app.gpt.service",
        "contract_review_app.gpt.clients.mock_client",
    ]
    for m in modules:
        sys.modules.pop(m, None)
    os.environ["LLM_PROVIDER"] = "mock"
    app_module = importlib.import_module("contract_review_app.api.app")
    return TestClient(app_module.app, headers={"x-schema-version": SCHEMA_VERSION})


def test_llm_mock_endpoints():
    client = _create_client()
    r1 = client.post("/api/gpt-draft", json={"text": "Example clause."})
    assert r1.status_code == 200
    r2 = client.post("/api/suggest_edits", json={"text": "Hi", "findings": []})
    assert r2.status_code == 200


def test_llm_mock_invalid_gpt_draft_payload():
    client = _create_client()
    resp = client.post("/api/gpt-draft", json={"clause_id": "only"})
    assert resp.status_code == 422
    assert isinstance(resp.json().get("detail"), list)
