from contract_review_app.core.lx_types import LxFeatureSet, LxSegment
from contract_review_app.legal_rules.dispatcher import select_candidate_rules


def _entity_offset_set(entries: list[dict]) -> set[tuple[int, int]]:
    spans: set[tuple[int, int]] = set()
    for entry in entries:
        start = entry.get("start")
        end = entry.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if end < start:
            continue
        spans.add((start, end))
    return spans


def _reason_offset_set(candidates, label: str, attr: str) -> set[tuple[int, int]]:
    spans: set[tuple[int, int]] = set()
    for candidate in candidates:
        for reason in getattr(candidate, "reasons", []) or []:
            if label not in getattr(reason, "labels", ()):  # tuple[str, ...]
                continue
            for entry in getattr(reason, attr, ()) or ():
                for span in getattr(entry, "offsets", ()) or ():
                    try:
                        start, end = int(span[0]), int(span[1])
                    except (TypeError, ValueError, IndexError):
                        continue
                    if end < start:
                        continue
                    spans.add((start, end))
    return spans


def test_dispatch_reasons_receive_feature_offsets():
    segment = LxSegment(
        segment_id=101,
        text="Supplier shall be paid USD 100. Payment is due within thirty days. "
        "This Agreement is governed by the laws of England and disputes belong to England courts.",
    )

    feature_set = LxFeatureSet(labels=["payment", "duration", "law", "jurisdiction"])
    feature_set.entities = {
        "amounts": [
            {
                "start": 20,
                "end": 27,
                "value": {"currency": "USD", "amount": 100},
            }
        ],
        "durations": [
            {
                "start": 46,
                "end": 56,
                "value": {"duration": "P30D", "days": 30},
            }
        ],
        "law": [
            {
                "start": 87,
                "end": 94,
                "value": {"code": "ENG"},
            }
        ],
        "jurisdiction": [
            {
                "start": 125,
                "end": 132,
                "value": {"code": "ENG"},
            }
        ],
    }
    # Force dispatcher to rely on entities for offsets.
    feature_set.amounts = []
    feature_set.durations = {}
    feature_set.law_signals = ["England"]
    feature_set.jurisdiction = "England"

    candidates = select_candidate_rules(segment, feature_set)
    assert candidates, "expected dispatcher candidates"

    expected_amount_offsets = _entity_offset_set(feature_set.entities["amounts"])
    expected_duration_offsets = _entity_offset_set(feature_set.entities["durations"])
    expected_law_offsets = _entity_offset_set(feature_set.entities["law"])
    expected_juris_offsets = _entity_offset_set(feature_set.entities["jurisdiction"])

    assert expected_amount_offsets
    assert expected_duration_offsets
    assert expected_law_offsets
    assert expected_juris_offsets

    reason_amount_offsets = _reason_offset_set(candidates, "amount", "amounts")
    reason_duration_offsets = _reason_offset_set(candidates, "duration", "durations")
    reason_law_offsets = _reason_offset_set(candidates, "law", "law")
    reason_juris_offsets = _reason_offset_set(
        candidates, "jurisdiction", "jurisdiction"
    )

    assert reason_amount_offsets == expected_amount_offsets
    assert reason_duration_offsets == expected_duration_offsets
    assert reason_law_offsets == expected_law_offsets
    assert reason_juris_offsets == expected_juris_offsets
