import re
from contract_review_app.intake.normalization import (
    normalize_for_intake,
    normalize_for_regex,
)


def test_mixed_language_and_punctuation():
    raw = "«Foo»\u00a0–\u00a0Привіт\tWorld"
    normalized = normalize_for_intake(raw)
    assert normalized == '"Foo" - Привіт World'


def test_regex_case_normalisation():
    raw = "“HELLO” — Привіт"
    pattern = re.compile(r'"hello" - привіт')
    norm = normalize_for_regex(raw, pattern)
    assert pattern.search(norm)
    pattern_i = re.compile(r'"HELLO" - Привіт', re.I)
    norm2 = normalize_for_regex(raw, pattern_i)
    assert pattern_i.search(norm2)
