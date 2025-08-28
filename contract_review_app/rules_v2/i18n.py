from __future__ import annotations

from typing import Dict

SUPPORTED = {"en", "uk"}  # extendable later


def validate_locale_dict(d: Dict[str, str]) -> None:
    """Ensure at least 'en' exists and values are non-empty strings; ignore extra keys."""
    if not isinstance(d, dict):
        raise TypeError("locale dict expected")
    if "en" not in d or not isinstance(d["en"], str) or d["en"].strip() == "":
        raise ValueError("locale dict must contain non-empty 'en'")
    for k, v in d.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise TypeError("locale dict keys/values must be strings")


def resolve_locale(d: Dict[str, str], prefer: str = "uk", fallback: str = "en") -> str:
    """Return d[prefer] if present/non-empty else d[fallback] if present else '' (deterministic)."""
    if not isinstance(d, dict):
        return ""
    val = (d.get(prefer) or "").strip()
    if val:
        return val
    val2 = (d.get(fallback) or "").strip()
    return val2


def resolve_bundle(
    bundle: Dict[str, Dict[str, str]],
    prefer: str = "uk",
    fallback: str = "en",
) -> Dict[str, str]:
    """Resolve a bundle of locale dicts -> flat strings. Expected keys: title, message, explain, suggestion."""
    out: Dict[str, str] = {}
    for k in ("title", "message", "explain", "suggestion"):
        d = bundle.get(k) or {}
        out[k] = resolve_locale(d, prefer=prefer, fallback=fallback)
    return out
