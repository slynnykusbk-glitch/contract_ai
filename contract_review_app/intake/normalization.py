"""Utilities for text normalization with offset mapping."""

from __future__ import annotations

import re
import unicodedata
from typing import List

# Mapping of various “smart” quotes/dashes and nbsp to ASCII equivalents.
# Specific replacements for compatibility.  Generic quote/dash normalisation is
# handled programmatically in ``_replace_char`` but we keep explicit entries for
# common cases and non-breaking spaces.
REPLACEMENTS = {
    "“": '"',
    "”": '"',
    "„": '"',
    "«": '"',
    "»": '"',
    "‚": '"',
    "‹": '"',
    "›": '"',
    "‘": "'",
    "’": "'",
    "‛": "'",
    "–": "-",
    "—": "-",
    "−": "-",
    "―": "-",
    "‑": "-",
    "‒": "-",
    "\u00a0": " ",
    "\u202f": " ",
}

_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def is_zero_width(ch: str) -> bool:
    """Return True if the character is a zero-width marker."""

    return ch in _ZERO_WIDTH


def _replace_char(ch: str) -> str:
    """Map ``ch`` to ASCII if it's a quote/dash or space variant."""

    if ch in REPLACEMENTS:
        return REPLACEMENTS[ch]
    cat = unicodedata.category(ch)
    if cat == "Pd":  # any kind of dash
        return "-"
    name = unicodedata.name(ch, "")
    if "QUOTE" in name or "QUOTATION MARK" in name or "GUILLEMET" in name:
        # Map based on single/double semantics; default to double quote.
        if "SINGLE" in name and "DOUBLE" not in name:
            return "'"
        return '"'
    return ch


def normalize_for_intake(text: str) -> str:
    """Return canonical form of ``text`` used by intake pipeline.

    - Unicode NFC normalization
    - Replace smart quotes/dashes with ASCII equivalents
    - NBSP (\u00a0) and tab -> regular space
    - Collapse runs of spaces into a single space
    - Convert CRLF/CR newlines into LF
    """

    if text is None:
        return ""

    # Canonical Unicode form and unified newlines
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace quotes/dashes/nbsp and collapse whitespace
    text = "".join(_replace_char(ch) for ch in text)
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    return text


def normalize_text(raw: str) -> tuple[str, List[int]]:
    """Normalize text and build a mapping from normalized to raw indices."""

    if raw is None:
        raw = ""

    normalized_chars: List[str] = []
    offset_map: List[int] = []

    prev_space = False
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]

        # Handle CRLF/CR -> LF preserving offset of first char
        if ch == "\r":
            offset_map.append(i)
            normalized_chars.append("\n")
            i += 1
            if i < n and raw[i] == "\n":
                i += 1
            prev_space = False
            continue

        if ch == "\n":
            offset_map.append(i)
            normalized_chars.append("\n")
            i += 1
            prev_space = False
            continue

        if is_zero_width(ch):
            i += 1
            continue

        ch = _replace_char(ch)

        if ch == "\t":
            ch = " "

        if ch == " ":
            if prev_space:
                i += 1
                continue
            prev_space = True
        else:
            prev_space = False

        normalized_chars.append(ch)
        offset_map.append(i)
        i += 1

    normalized_text = unicodedata.normalize("NFC", "".join(normalized_chars))

    assert len(offset_map) == len(normalized_text)
    for i in range(1, len(offset_map)):
        assert offset_map[i - 1] <= offset_map[i]
    for j in offset_map:
        assert 0 <= j < len(raw)

    return normalized_text, offset_map


def normalize_for_regex(text: str, pattern: re.Pattern[str]) -> str:
    """Normalise ``text`` for regex matching.

    In addition to ``normalize_for_intake`` this lowercases the text if the
    pattern does not enable case-insensitive matching (neither ``re.IGNORECASE``
    flag nor an inline ``(?i)`` modifier).
    """

    norm = normalize_for_intake(text)
    has_i = bool(pattern.flags & re.IGNORECASE or "(?i" in pattern.pattern)
    return norm if has_i else norm.lower()
