import pytest
import pytest

from contract_review_app.engine.suggest import suggest_edits


def _get_first_edit(text: str, clause_type: str):
    res = suggest_edits(text, clause_type=clause_type)
    assert isinstance(res.get("edits"), list)
    assert res["edits"], f"no edits for {clause_type}"
    return res["edits"][0]


@pytest.mark.parametrize(
    "clause_type,text,mode",
    [
        ("governing_law", "This contract is governed by the laws of Mars.", "replace"),
        ("dispute_resolution", "Disputes will be handled informally.", "insert"),
        ("termination_convenience", "Either party may terminate for convenience with 30 days notice.", "insert"),
        ("liability_cap", "Liability capped at 100.", "insert"),
        ("insurance_noncompliance", "If the Supplier fails to maintain insurance, the Customer may claim damages.", "insert"),
        ("export_hmrc", "The Supplier shall comply with export controls.", "insert"),
        ("placeholder_police", "The amount is [●] GBP.", "replace_pattern"),
        ("notices", "All notices shall be served in writing.", "replace"),
        ("confidentiality", "The parties shall keep information confidential.", "insert"),
    ],
)
def test_templates_produce_edit(clause_type, text, mode):
    edit = _get_first_edit(text, clause_type)
    rng = edit["range"]
    assert {"start", "length"}.issubset(rng.keys())
    if mode == "replace":
        assert rng["start"] == 0
        assert rng["length"] == len(text)
    elif mode == "insert":
        assert rng["start"] == len(text)
        assert rng["length"] == 0
    elif mode == "replace_pattern":
        pos = text.index("[●]")
        assert rng["start"] == pos
        assert rng["length"] == len("[●]")
    assert isinstance(edit.get("replacement"), str)
    assert edit["replacement"] != "[object Object]"
