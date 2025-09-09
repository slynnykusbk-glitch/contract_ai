import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def test_trace_contains_doctype_and_clauses():
    os.environ.setdefault("LLM_PROVIDER", "mock")
    client = TestClient(app)
    text = (
        "NON-DISCLOSURE AGREEMENT\n"
        "Confidentiality. Each party agrees to keep all information confidential.\n"
        "Governing Law. This agreement is governed by the laws of England.\n"
    )
    headers = {"x-schema-version": SCHEMA_VERSION}
    resp = client.post("/api/analyze", json={"text": text}, headers=headers)
    assert resp.status_code == 200
    cid = resp.headers["x-cid"]
    trace = client.get(f"/api/trace/{cid}").json()
    classifiers = trace.get("classifiers")
    assert classifiers is not None
    assert classifiers.get("document_type") == "NDA"
    assert "confidentiality" in classifiers.get("clause_types", [])
    assert classifiers.get("active_rule_packs")
    assert "language" in classifiers
