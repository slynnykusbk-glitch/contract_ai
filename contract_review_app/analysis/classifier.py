from __future__ import annotations

import re
from typing import Dict, List

from contract_review_app.legal_rules import loader

# Mapping of clause types to regex patterns used for detection.
# Patterns are searched in both heading and text of a segment.
_CLAUSE_PATTERNS: Dict[str, List[re.Pattern[str]]] = {
    "governing_law": [
        re.compile(r"governing\s+law", re.I),
        re.compile(r"choice\s+of\s+law", re.I),
    ],
    "confidentiality": [
        re.compile(r"confidential", re.I),
        re.compile(r"non[-\s]?disclosure", re.I),
    ],
    "limitation_of_liability": [
        re.compile(r"limitation\s+of\s+liabilit", re.I),
        re.compile(r"limit[^\n]{0,40}liabilit", re.I),
        re.compile(r"liabilit", re.I),
    ],
    "intellectual_property": [
        re.compile(r"intellectual\s+property", re.I),
        re.compile(r"\bipr\b", re.I),
    ],
    "data_protection": [
        re.compile(r"data\s+protection", re.I),
        re.compile(r"\bgdpr\b", re.I),
        re.compile(r"personal\s+data", re.I),
    ],
    "dispute_resolution": [
        re.compile(r"dispute\s+resolution", re.I),
        re.compile(r"jurisdiction", re.I),
        re.compile(r"arbitration", re.I),
        re.compile(r"courts?", re.I),
    ],
    "definitions": [
        re.compile(r"definitions", re.I),
        re.compile(r"interpretation", re.I),
    ],
    "parties": [
        re.compile(r"parties", re.I),
    ],
}


def _detect_clause(text: str) -> str | None:
    """Return clause_type inferred from *text* or ``None``."""
    for ctype, pats in _CLAUSE_PATTERNS.items():
        for pat in pats:
            if pat.search(text):
                return ctype
    return None


def classify_segments(segments: List[Dict]) -> None:
    """Enrich *segments* in-place with ``clause_type`` and rule findings.

    For each segment a ``clause_type`` is inferred from its heading/text.  If a
    type is determined, deterministic YAML rules are executed against the
    segment's text and any matching findings are stored under ``findings``.
    """

    for seg in segments:
        heading = seg.get("heading") or ""
        text = seg.get("text") or ""
        combined = f"{heading} {text}".lower()

        clause_type = _detect_clause(combined)
        seg["clause_type"] = clause_type

        if not clause_type:
            continue

        # Execute deterministic rules and retain only those matching this clause
        # type.  The loader returns findings already structured with ``scope``
        # and ``occurrences`` fields, which we keep untouched.
        findings = loader.match_text(text)
        seg["findings"] = [
            f for f in findings if f.get("clause_type") == clause_type
        ]
