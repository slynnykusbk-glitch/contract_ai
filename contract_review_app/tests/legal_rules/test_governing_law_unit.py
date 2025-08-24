from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules import governing_law as gl


def _mk_input(txt: str) -> AnalysisInput:
    return AnalysisInput(clause_type="governing_law", text=txt, metadata={"t": "unit"})


def test_ok_england_and_wales_with_conflict_exclusion():
    txt = (
        "This Agreement shall be governed by and construed in accordance with the laws of "
        "England and Wales, excluding its conflict of laws rules. The parties submit to the "
        "non-exclusive jurisdiction of the courts of England."
    )
    out = gl.analyze(_mk_input(txt))

    assert out.status in {
        "OK",
        "WARN",
    }  # має бути OK; якщо знайдено середні зауваження — WARN
    assert out.status == "OK"
    assert any("посилання на право" in f.message.lower() for f in out.findings)
    assert out.diagnostics.get("rule") == gl.RULE_NAME
    assert len(out.diagnostics.get("citations", [])) > 0


def test_warn_jurisdiction_only_no_governing_law():
    txt = (
        "The parties submit to the exclusive jurisdiction of the courts of England and Wales. "
        "Venue shall be London."
    )
    out = gl.analyze(_mk_input(txt))

    assert out.status == "WARN"
    # має бути зауваження про відсутність явного права
    issues = " | ".join(f.message.lower() for f in out.findings)
    assert (
        "без явного застосовного права" in issues
        or "не вдалося однозначно ідентифікувати" in issues
    )


def test_fail_no_clause_at_all():
    txt = "The parties agree to cooperate in good faith to implement the project milestones."
    out = gl.analyze(_mk_input(txt))

    assert out.status == "FAIL"
    assert any("відсутня або неявна" in f.message.lower() for f in out.findings)
    # підказки/рекомендації повинні бути
    assert len(out.recommendations) >= 1
