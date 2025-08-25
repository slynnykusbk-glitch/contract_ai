from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def _find(findings, rule_id):
    for f in findings:
        if f.get("rule_id") == rule_id:
            return f
    return None


def test_missing_exhibit_m_triggers_high_severity():
    text = (
        "This Agreement includes Exhibit L attached hereto. "
        "Another appendix is referenced but a second exhibit is never mentioned."
    )
    resp = client.post("/api/analyze", json={"text": text, "language": "en"})
    assert resp.status_code == 200
    data = resp.json()
    finding = _find(data["analysis"]["findings"], "exhibits_LM_referenced")
    assert finding is not None
    assert finding.get("severity") == "high"


def test_process_agent_undefined_term_flagged():
    text = "All notices shall be delivered to the Process Agent in London."
    resp = client.post("/api/analyze", json={"text": text, "language": "en"})
    assert resp.status_code == 200
    data = resp.json()
    finding = _find(data["analysis"]["findings"], "definitions_undefined_used")
    assert finding is not None
    assert "Process Agent" in finding.get("message", "")
