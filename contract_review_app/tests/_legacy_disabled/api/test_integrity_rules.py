from contract_review_app.api.app import _analyze_document


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
    data = _analyze_document(text)
    finding = _find(data.get("findings", []), "exhibits_LM_referenced")
    assert finding is not None
    assert finding.get("severity") == "high"


def test_process_agent_undefined_term_flagged():
    text = "All notices shall be delivered to the Process Agent in London."
    data = _analyze_document(text)
    finding = _find(data.get("findings", []), "definitions_undefined_used")
    assert finding is not None
    assert "Process Agent" in finding.get("message", "")
