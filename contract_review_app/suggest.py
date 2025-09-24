"""Utilities for building deterministic edit operations for API responses."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


_REPLACEMENT_TEXT = "This Agreement shall be governed by the laws of England and Wales."
_NOTE_REPLACE = "Normalize governing law wording; check policy consistency."
_NOTE_INSERT = "Add missing governing law clause."


def _extract_span(candidate: Any) -> Optional[Tuple[int, int]]:
    """Attempt to extract a (start, end) tuple from arbitrary finding objects."""
    if candidate is None:
        return None
    span: Any
    if hasattr(candidate, "span"):
        span = getattr(candidate, "span")
    else:
        span = candidate
    if span is None:
        return None
    if isinstance(span, dict):
        try:
            start = int(span.get("start") or 0)
        except Exception:
            start = 0
        if "length" in span:
            try:
                length = int(span.get("length") or 0)
            except Exception:
                length = 0
            end = start + max(0, length)
        else:
            try:
                end = int(span.get("end") or start)
            except Exception:
                end = start
        return (max(0, start), max(0, end))
    if isinstance(span, (list, tuple)) and len(span) == 2:
        try:
            start = int(span[0] or 0)
        except Exception:
            start = 0
        try:
            end = int(span[1] or start)
        except Exception:
            end = start
        return (max(0, start), max(0, end))
    if hasattr(span, "start") and hasattr(span, "end"):
        try:
            start = int(getattr(span, "start") or 0)
        except Exception:
            start = 0
        try:
            end = int(getattr(span, "end") or start)
        except Exception:
            end = start
        return (max(0, start), max(0, end))
    return None


def build_edits(
    text: str, clause_type: str, findings: Iterable[Any], mode: str
) -> List[Dict[str, Any]]:
    """Construct a list of edit operations for the given clause type.

    Ranges are character-based indices on the provided ``text``.
    """
    if clause_type != "governing_law":
        return []

    span: Optional[Tuple[int, int]] = None
    for f in findings or []:
        f_ct = None
        if isinstance(f, dict):
            f_ct = f.get("clause_type") or f.get("clause")
            cand = f.get("span") or f.get("range")
        else:
            f_ct = getattr(f, "clause_type", None)
            cand = getattr(f, "span", None) or getattr(f, "range", None)
        if f_ct == clause_type:
            span = _extract_span(cand)
            if span:
                break

    if span:
        start, end = span
        start = max(0, min(len(text), start))
        end = max(start, min(len(text), end))
        return [
            {
                "range": {"start": start, "length": end - start},
                "replacement": _REPLACEMENT_TEXT,
                "note": _NOTE_REPLACE,
            }
        ]

    return [
        {
            "range": {"start": len(text), "length": 0},
            "replacement": _REPLACEMENT_TEXT,
            "note": _NOTE_INSERT,
        }
    ]
