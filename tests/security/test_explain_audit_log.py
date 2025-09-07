import json
import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def _read_audit():
    with open("var/audit.log", "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def test_explain_audit_log(tmp_path):
    if os.path.exists("var/audit.log"):
        os.remove("var/audit.log")
    req = {
        "finding": {
            "code": "uk_ucta_2_1_invalid",
            "message": "Exclusion of liability for personal injury",
            "span": {"start": 0, "end": 10},
        },
        "text": "Exclusion of liability for personal injury is void.",
    }
    resp = client.post("/api/explain", json=req)
    assert resp.status_code == 200
    lines = _read_audit()
    assert lines
    rec = lines[-1]
    assert rec["event"] == "explain"
    assert rec.get("citations_count") >= 1
    assert rec.get("evidence_count") >= 0
    assert rec.get("rule_code") == "uk_ucta_2_1_invalid"
    assert "doc_hash" in rec
