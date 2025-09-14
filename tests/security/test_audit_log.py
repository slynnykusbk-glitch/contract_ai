import json
import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app


client = TestClient(app)


def _read_audit_lines():
    with open("var/audit.log", "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_audit_events_written(tmp_path):
    # ensure clean log
    if os.path.exists("var/audit.log"):
        os.remove("var/audit.log")

    r1 = client.post("/api/analyze", json={"text": "Hello"})
    assert r1.status_code == 200
    cid = r1.headers.get("x-cid")
    r2 = client.post("/api/gpt-draft", json={"clause_id": cid, "text": "Draft clause"})
    assert r2.status_code == 200
    r3 = client.post("/api/suggest_edits", json={"text": "Hello"})
    assert r3.status_code == 200

    lines = _read_audit_lines()
    events = {line["event"]: line for line in lines}
    assert "analyze" in events
    assert "gpt_draft" in events
    assert "suggest_edits" in events

    assert "findings_count" in events["analyze"]
    assert "rules_count" in events["analyze"]
    assert "before_text_len" in events["gpt_draft"]
    assert "after_text_len" in events["gpt_draft"]
    assert "suggestions_count" in events["suggest_edits"]
    assert "ops_count" in events["suggest_edits"]
