from contract_review_app.legal_rules.dispatcher import (
    ReasonAmount,
    ReasonCodeRef,
    ReasonDuration,
    ReasonPayload,
)
from contract_review_app.trace_artifacts import serialize_reason_entry


def test_serialize_reason_entry_offsets_and_types():
    reason = ReasonPayload(
        labels=("amount", "law"),
        amounts=(
            ReasonAmount(currency="GBP", value=10000, offsets=((10, 16), (30, 36))),
        ),
        durations=(ReasonDuration(unit="days", value=30, offsets=((40, 48),)),),
        law=(ReasonCodeRef(code="ENG", offsets=((50, 58),)),),
        jurisdiction=(ReasonCodeRef(code="ENG", offsets=((60, 68),)),),
    )

    payload = serialize_reason_entry(reason)

    assert payload["labels"] == ["amount", "law"]

    assert payload["amounts"] == [
        {"ccy": "GBP", "value": 10000, "offsets": [[10, 16], [30, 36]]}
    ]
    assert payload["durations"] == [
        {"unit": "days", "value": 30, "offsets": [[40, 48]]}
    ]
    assert payload["law"] == [{"code": "ENG", "offsets": [[50, 58]]}]
    assert payload["jurisdiction"] == [{"code": "ENG", "offsets": [[60, 68]]}]

    for key in ("amounts", "durations", "law", "jurisdiction"):
        for entry in payload[key]:
            offsets = entry["offsets"]
            assert isinstance(offsets, list) and offsets
            for span in offsets:
                assert isinstance(span, list)
                assert len(span) == 2
                assert all(isinstance(val, int) for val in span)
            unwanted = {field.lower() for field in entry.keys()}
            assert "text" not in unwanted
            assert "raw" not in unwanted

