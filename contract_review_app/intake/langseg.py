from __future__ import annotations

from typing import Dict, List


_LATIN_RANGES = [
    (0x0080, 0x00FF),
    (0x0100, 0x017F),
    (0x0180, 0x024F),
    (0x1E00, 0x1EFF),
]
_CYRILLIC_RANGES = [
    (0x0400, 0x04FF),
    (0x0500, 0x052F),
    (0x2DE0, 0x2DFF),
    (0xA640, 0xA69F),
]
_GREEK_RANGES = [
    (0x0370, 0x03FF),
    (0x1F00, 0x1FFF),
]
_ARABIC_RANGES = [
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
]
_HEBREW_RANGES = [(0x0590, 0x05FF)]


def _in_ranges(cp: int, ranges: List[tuple[int, int]]) -> bool:
    return any(start <= cp <= end for start, end in ranges)


def detect_script(ch: str) -> str:
    """Return script label for a single character using Unicode ranges.
    Returns: one of {"Latin","Cyrillic","Greek","Arabic","Hebrew","Common"}.
    """

    if not ch:
        return "Common"

    cp = ord(ch)

    if ch.isalpha():
        if cp <= 0x007F:
            return "Latin"
        if _in_ranges(cp, _LATIN_RANGES):
            return "Latin"
        if _in_ranges(cp, _CYRILLIC_RANGES):
            return "Cyrillic"
        if _in_ranges(cp, _GREEK_RANGES):
            return "Greek"
        if _in_ranges(cp, _ARABIC_RANGES):
            return "Arabic"
        if _in_ranges(cp, _HEBREW_RANGES):
            return "Hebrew"
    return "Common"


def script_to_lang(script: str) -> str:
    """Map script to lightweight language tag. Deterministic and total mapping."""

    mapping = {
        "Latin": "en",
        "Cyrillic": "uk",
        "Greek": "el",
        "Arabic": "ar",
        "Hebrew": "he",
        "Common": "und",
    }
    return mapping[script]


def segment_lang_script(text: str) -> List[Dict[str, object]]:
    """Return list of segments [{start:int, end:int, lang:str, script:str}] for the whole text.
    - start inclusive, end exclusive
    - segments are contiguous and non-overlapping
    - merges adjacent runs with same (lang, script)
    - O(n) single pass
    """

    if not text:
        return []

    segments: List[Dict[str, object]] = []
    start = 0
    current_script = detect_script(text[0])
    current_lang = script_to_lang(current_script)

    for idx in range(1, len(text)):
        ch = text[idx]
        script = detect_script(ch)
        if script != current_script:
            segments.append(
                {
                    "start": start,
                    "end": idx,
                    "script": current_script,
                    "lang": current_lang,
                }
            )
            start = idx
            current_script = script
            current_lang = script_to_lang(script)

    segments.append(
        {
            "start": start,
            "end": len(text),
            "script": current_script,
            "lang": current_lang,
        }
    )
    return segments
