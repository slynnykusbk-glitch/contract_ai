import pytest
from contract_review_app.core.schemas import SuggestEdit


def test_suggest_edit_old_json_valid_and_auto_operations():
    payload = {
        "span": {"start": 0, "length": 5},
        "insert": "new",
        "delete": "old",
        "rationale": "because",
        "citations": [{"instrument": "Act", "section": "1"}],
    }
    se = SuggestEdit.model_validate(payload)
    assert se.operations == ["replace"]
    dumped = se.model_dump(exclude_none=True)
    assert dumped["insert"] == "new"
    assert dumped["delete"] == "old"


def test_suggest_edit_new_fields_valid():
    payload = {
        "span": {"start": 1, "length": 2},
        "insert": "b",
        "rationale": "reason",
        "citations": [],
        "evidence": ["source"],
        "verification_status": "verified",
        "flags": ["f1"],
        "operations": ["comment"],
    }
    se = SuggestEdit.model_validate(payload)
    assert se.evidence == ["source"]
    assert se.verification_status == "verified"
    assert se.flags == ["f1"]
    assert se.operations == ["comment"]


def test_suggest_edit_auto_operations_on_insert_delete():
    payload = {
        "span": {"start": 0, "length": 1},
        "delete": "x",
        "rationale": "r",
        "citations": [],
    }
    se = SuggestEdit.model_validate(payload)
    assert se.operations == ["replace"]
