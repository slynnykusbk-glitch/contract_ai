"""Utilities for text normalization with offset mapping."""

from __future__ import annotations

REPLACEMENTS = {
    "“": '"',
    "”": '"',
    "«": '"',
    "»": '"',
    "‚": '"',
    "‘": '"',
    "’": '"',
    "–": "-",
    "—": "-",
    "−": "-",
    "\u00a0": " ",
    "\u202f": " ",
}

_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def is_zero_width(ch: str) -> bool:
    """Return True if the character is a zero-width marker."""

    return ch in _ZERO_WIDTH


def normalize_text(raw: str) -> tuple[str, list[int]]:
    """Normalize text and build a mapping from normalized to raw indices."""

    normalized_chars: list[str] = []
    offset_map: list[int] = []

    for idx, ch in enumerate(raw):
        if is_zero_width(ch):
            continue
        normalized_chars.append(REPLACEMENTS.get(ch, ch))
        offset_map.append(idx)

    normalized_text = "".join(normalized_chars)

    assert len(offset_map) == len(normalized_text)
    for i in range(1, len(offset_map)):
        assert offset_map[i - 1] <= offset_map[i]
    for j in offset_map:
        assert 0 <= j < len(raw)

    return normalized_text, offset_map
