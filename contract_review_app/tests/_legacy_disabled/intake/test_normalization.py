import random

import pytest

from contract_review_app.intake.normalization import REPLACEMENTS, normalize_text


def assert_invariants(raw: str, normalized: str, offset_map: list[int]) -> None:
    assert len(offset_map) == len(normalized)
    assert all(0 <= j < len(raw) for j in offset_map)
    assert all(offset_map[i] <= offset_map[i + 1] for i in range(len(offset_map) - 1))
    for i, j in enumerate(offset_map):
        raw_ch = raw[j]
        norm_ch = normalized[i]
        if raw_ch != norm_ch:
            assert REPLACEMENTS.get(raw_ch) == norm_ch


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Quote: “Test”.", 'Quote: "Test".'),
        ("Hello\u00a0World", "Hello World"),
        ("A–B—C−D", "A-B-C-D"),
    ],
)
def test_basic_replacements(raw: str, expected: str) -> None:
    normalized, offset_map = normalize_text(raw)
    assert normalized == expected
    assert offset_map == list(range(len(raw)))
    assert_invariants(raw, normalized, offset_map)


def test_zero_width_removal() -> None:
    raw = "A\u200bB"
    normalized, offset_map = normalize_text(raw)
    assert normalized == "AB"
    assert offset_map == [0, 2]
    assert_invariants(raw, normalized, offset_map)


def test_emoji_preserved() -> None:
    raw = "Cool 👍!"
    normalized, offset_map = normalize_text(raw)
    assert normalized == raw
    assert offset_map == list(range(len(raw)))
    assert_invariants(raw, normalized, offset_map)


def test_idempotence() -> None:
    raw = "Hello “World”"
    normalized, offset_map1 = normalize_text(raw)
    again, offset_map2 = normalize_text(normalized)
    assert again == normalized
    assert offset_map2 == list(range(len(normalized)))
    assert_invariants(raw, normalized, offset_map1)
    assert_invariants(normalized, again, offset_map2)


def test_mixed_input() -> None:
    raw = 'Hello “World” — Привіт "Світ" \u200d✅'
    expected = 'Hello "World" - Привіт "Світ" ✅'
    normalized, offset_map = normalize_text(raw)
    assert normalized == expected
    assert_invariants(raw, normalized, offset_map)


def _random_char() -> str:
    while True:
        cp = random.randint(0, 0x10FFFF)
        if 0xD800 <= cp <= 0xDFFF:
            continue
        return chr(cp)


def test_random_unicode() -> None:
    random.seed(0)
    for _ in range(20):
        length = random.randint(0, 512)
        raw = "".join(_random_char() for _ in range(length))
        normalized, offset_map = normalize_text(raw)
        assert_invariants(raw, normalized, offset_map)
