from contract_review_app.legal_rules import loader


def test_gl_jurisdiction_conflict():
    text = (
        "This Agreement is governed by the laws of England and Wales and the parties submit to the exclusive jurisdiction of the Scottish courts."
    )
    loader.load_rule_packs()
    findings = loader.match_text(text)
    assert any(f["rule_id"] == "gl_jurisdiction_conflict" for f in findings)
