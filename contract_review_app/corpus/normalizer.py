from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any


_RE_WS = re.compile(r"\s+")

_REPLACEMENTS = {
    "\u00A0": " ",
    "\u201C": '"',
    "\u201D": '"',
    "\u2018": "'",
    "\u2019": "'",
}


def normalize_text(text: str) -> str:
    """Normalize text for storage and checksum calculation."""
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = _RE_WS.sub(" ", text)
    return text.strip()


def utc_iso(value: Any) -> str:
    """Return ISO 8601 UTC string for given datetime or string."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("expected datetime or ISO string")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def checksum_for(*parts: str) -> str:
    """Compute checksum for given string parts."""
    h = hashlib.sha256()
    for part in parts:
        h.update((part or "").encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()
