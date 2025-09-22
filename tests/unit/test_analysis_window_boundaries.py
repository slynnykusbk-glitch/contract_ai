from __future__ import annotations

from contract_review_app.analysis import resolve_labels


def test_analysis_window_preserves_word_boundaries() -> None:
    prefix = "A" * 950
    body = "\nService Level Agreement\n"
    suffix = "B" * 876
    text = prefix + body + suffix

    result = resolve_labels(text, None)

    assert "service_levels_sla" in result
