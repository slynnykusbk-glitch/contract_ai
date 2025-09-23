import re

from contract_review_app.legal_rules.engine import analyze


def test_finding_inherits_channel_salience_from_spec():
    text = "Important clause."
    rule_with_channel = {
        "id": "R-CHAN",
        "patterns": [re.compile(r"Important")],
        "severity": "medium",
        "channel": "Policy",
        "salience": 70,
    }

    findings = analyze(text, [rule_with_channel])

    assert len(findings) == 1
    finding = findings[0]
    assert finding["channel"] == "Policy"
    assert finding["salience"] == 70

    rule_default_salience = {
        "id": "R-DEFAULT",
        "patterns": [re.compile(r"clause")],
        "severity": "medium",
    }

    default_findings = analyze(text, [rule_default_salience])

    assert len(default_findings) == 1
    default_finding = default_findings[0]
    assert "channel" not in default_finding
    assert default_finding["salience"] == 50
