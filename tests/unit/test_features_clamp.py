from contract_review_app.trace_artifacts import (
    MAX_AMOUNTS_PER_SEG,
    MAX_DURATIONS_PER_SEG,
    MAX_ENTITY_VALUES_PER_KEY,
    MAX_LABELS_PER_SEG,
    build_features,
)


class _DocStub:
    normalized_text = "x" * 100
    language = "en"
    segments = [{"lang": "en"}]


_SEGMENT = {
    "id": 1,
    "start": 0,
    "end": 10,
    "clause_type": "type",
    "labels": [f"label-{i}" for i in range(32)],
    "entities": {
        "amounts": [f"{i}" for i in range(40)],
        "durations": [{"days": i} for i in range(40)],
        "custom": [f"item-{i}" for i in range(50)],
    },
}


def test_entities_lists_are_clamped():
    payload = build_features(_DocStub(), [_SEGMENT])

    segment = payload["segments"][0]
    entities = segment["entities"]

    assert len(segment["labels"]) == MAX_LABELS_PER_SEG
    assert len(entities["amounts"]) == MAX_AMOUNTS_PER_SEG
    assert len(entities["durations"]) == MAX_DURATIONS_PER_SEG
    assert len(entities["custom"]) == MAX_ENTITY_VALUES_PER_KEY
