from contract_review_app.engine.suggest import build_edits


def test_build_edits_governing_law():
    text = "The parties agree to work together."
    findings = [
        {
            "code": "GL-ABSENT",
            "message": "No explicit governing law statement",
            "severity": "critical",
            "span": {"start": 0, "length": 0},
        }
    ]
    edits = build_edits(text, findings, "friendly")
    assert isinstance(edits, list)
    assert len(edits) >= 1
