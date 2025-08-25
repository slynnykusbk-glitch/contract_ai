from __future__ import annotations
from typing import Dict, Any


def pick_suggest_text(data: Dict[str, Any], profile: str) -> str:
    """Return suggestion text for profile with friendly fallback."""
    if not isinstance(data, dict):
        return ""
    profile = (profile or "friendly").lower().strip()
    return str(data.get(profile) or data.get("friendly") or "")
