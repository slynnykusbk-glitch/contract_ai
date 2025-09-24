import pytest
from contract_review_app.api.models import SCHEMA_VERSION


def test_e2e_smoke(api):
    # Health check
    r = api.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("schema") == SCHEMA_VERSION
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION

    # Analyze document
    r = api.post("/api/analyze", json={"text": "Hello world", "language": "en-GB"})
    assert r.status_code == 200
    cid = r.headers.get("x-cid")
    assert cid
    analysis = r.json()["analysis"]
    findings = analysis.get("findings", [])
    keys = {(f.get("rule_id"), f.get("start"), f.get("end")) for f in findings}
    assert len(keys) == len(findings)
    assert analysis.get("duplicates_removed", 0) >= 0

    # Trace and report
    r_trace = api.get(f"/api/trace/{cid}")
    assert r_trace.status_code == 200
    r_report = api.get(f"/api/report/{cid}.html")
    assert r_report.status_code in {200, 404}

    # Summary
    r_summary = api.post("/api/summary", json={"cid": cid})
    assert r_summary.status_code == 200

    # GPT draft
    payload = {"clause_id": cid, "text": "Ping", "mode": "friendly"}
    r_draft = api.post("/api/gpt-draft", json=payload)
    assert r_draft.status_code == 200
    assert r_draft.json().get("draft_text", "").strip()
