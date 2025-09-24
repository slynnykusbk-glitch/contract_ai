import os
import sys
import importlib
import pytest
from fastapi.testclient import TestClient


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
    os.environ.setdefault("LLM_PROVIDER", "mock")
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)
    from contract_review_app.api.models import SCHEMA_VERSION

    client = TestClient(app_module.app, headers={"x-schema-version": SCHEMA_VERSION})
    return client, modules


@pytest.fixture()
def client():
    client, modules = _create_client()
    try:
        yield client
    finally:
        for m in modules:
            sys.modules.pop(m, None)


TEXT = (
    "NON-DISCLOSURE AGREEMENT\n"
    "Confidential Information may be used only for the Permitted Purpose."
)


def test_summary_returns_doc_type_and_confidence(client):
    r_analyze = client.post("/api/analyze", json={"text": TEXT})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    resp = client.post("/api/summary", json={"cid": cid})
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["type"] == "NDA"
    assert isinstance(summary.get("type_confidence"), float)
    assert summary["type_confidence"] >= 0.0


def test_analyze_returns_type_confidence_and_candidates(client):
    resp = client.post("/api/analyze", json={"text": TEXT})
    assert resp.status_code == 200
    summary = resp.json()["results"]["summary"]
    assert summary["type"] == "NDA"
    assert isinstance(summary.get("type_confidence"), float)
    cand = summary.get("debug", {}).get("doctype_top")
    assert (
        isinstance(cand, list)
        and cand
        and all("type" in c and "score" in c for c in cand)
    )
    assert cand[0]["type"] == "NDA"
