from contract_review_app.core.normalize import normalize_with_offsets


def test_normalize_with_offsets() -> None:
    raw = "“Hello\u00a0World”—she\u202fsaid–indeed"
    normalized, offsets = normalize_with_offsets(raw)
    assert normalized == '"Hello World"-she said-indeed'
    assert offsets == list(range(len(raw)))
