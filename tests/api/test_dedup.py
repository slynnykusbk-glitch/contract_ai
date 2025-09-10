import re
from contract_review_app.legal_rules import engine


def test_engine_dedup_removes_duplicates():
    rule = {"id": "R1", "patterns": [re.compile("foo")], "severity": "major"}
    findings = engine.analyze("foo", [rule, rule])
    assert len(findings) == 1
    f = findings[0]
    assert f["rule_id"] == "R1"
    assert f["start"] == 0 and f["end"] > 0
