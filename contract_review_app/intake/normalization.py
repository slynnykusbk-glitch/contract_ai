"""Utilities for text normalization with offset mapping."""

from __future__ import annotations

import re
import unicodedata
from typing import List

# Mapping of various “smart” quotes/dashes and nbsp to ASCII equivalents.
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


def normalize_for_intake(text: str) -> str:
    """Return canonical form of ``text`` used by intake pipeline.

    - Unicode NFC normalization
    - Replace smart quotes/dashes with ASCII equivalents
    - NBSP (\u00A0) and tab -> regular space
    - Collapse runs of spaces into a single space
    - Convert CRLF/CR newlines into LF
    """

    if text is None:
        return ""

    # Canonical Unicode form and unified newlines
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace smart quotes/dashes and nbsp
    for src, dst in REPLACEMENTS.items():
        text = text.replace(src, dst)

    # Tabs to space and collapse multiple spaces
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

        ch = REPLACEMENTS.get(ch, ch)

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
