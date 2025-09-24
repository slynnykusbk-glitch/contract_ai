from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Tuple


# Regular expression patterns for simple PII detection. They intentionally use
# broad matches because the goal is to avoid leaking obvious identifiers to
# external LLM providers rather than perfect PII detection.
_PATTERNS = {
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.I),
    # +44 1234 567890, (123)456-7890, 123-456-7890 etc.
    "PHONE": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    # National Insurance number: two letters, six digits, final letter A-D
    "NI": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.I),
    # Simplified UK postcode pattern
    "POSTCODE": re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b", re.I),
    # Dates like 01/02/2024 or 2024-02-01
    "DATE": re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"),
    # Very naive full name (two or three capitalised words)
    # Avoid common leading words such as 'Contact' which are not part of the
    # actual name by using a negative lookahead.
    "NAME": re.compile(
        r"\b(?!Contact\b)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
}


def _substitute(
    text: str,
    pattern: re.Pattern[str],
    token_prefix: str,
    pii_map: Dict[str, str],
    counters: Dict[str, int],
) -> str:
    def repl(match: re.Match[str]) -> str:
        token = f"<{token_prefix}_{counters[token_prefix]}>"
        counters[token_prefix] += 1
        pii_map[token] = match.group(0)
        return token

    return pattern.sub(repl, text)


def redact_pii(text: str) -> Tuple[str, Dict[str, str]]:
    """Redact common PII from *text*.

    Returns a tuple of ``(redacted_text, pii_map)`` where ``pii_map`` maps
    placeholder tokens to their original values.
    """

    pii_map: Dict[str, str] = {}
    counters: Dict[str, int] = defaultdict(int)
    redacted = text
    for typ, pattern in _PATTERNS.items():
        redacted = _substitute(redacted, pattern, typ, pii_map, counters)
    return redacted, pii_map


def scrub_llm_output(text: str, pii_map: Dict[str, str]) -> str:
    """Ensure that no original PII values leak in *text*.

    If any of the original values appear, replace them with the corresponding
    placeholder tokens from ``pii_map``.
    """

    if not text:
        return text
    scrubbed = text
    for token, original in pii_map.items():
        scrubbed = scrubbed.replace(original, token)
    return scrubbed


__all__ = ["redact_pii", "scrub_llm_output"]
