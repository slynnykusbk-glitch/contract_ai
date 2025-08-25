from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Dict

_POLICIES: Dict[str, Dict[str, Any]] | None = None


def _load() -> Dict[str, Dict[str, Any]]:
    global _POLICIES
    if _POLICIES is None:
        path = Path(__file__).resolve().parent / "policies.yaml"
        try:
            _POLICIES = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            _POLICIES = {}
    return _POLICIES


def get_policy(profile: str) -> Dict[str, Any]:
    data = _load()
    profile = (profile or "friendly").lower().strip()
    return data.get(profile, data.get("friendly", {}))
