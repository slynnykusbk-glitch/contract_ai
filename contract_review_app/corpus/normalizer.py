"""Utilities for normalising text and timestamps in the corpus."""

from __future__ import annotations

import re
import unicodedata
from hashlib import sha256
from datetime import datetime, timezone
from typing import Iterable


SPACE_RE = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    """Return a canonical representation of ``s``.

    Performs Unicode NFKC normalisation, replaces non-breaking spaces,
    collapses whitespace, trims and normalises quotes.
    """

    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = SPACE_RE.sub(" ", s)
    return s.strip()


def utc_iso(dt: str | datetime) -> datetime:
    """Parse ``dt`` as an aware UTC ``datetime``."""

    if isinstance(dt, str):
        dt = dt.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def checksum_for(*parts: str) -> str:
    """Return SHA256 checksum for the concatenated parts."""

    joined = "||".join(parts)
    return sha256(joined.encode("utf-8")).hexdigest()
