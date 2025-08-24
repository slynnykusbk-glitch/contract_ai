from __future__ import annotations

"""Utilities for rule-based text suggestions and edit generation."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

# Lazily loaded suggestions mapping
_SUGGEST_DATA: Dict[str, Any] | None = None


def _load_suggest_data() -> Dict[str, Any]:
    global _SUGGEST_DATA
    if _SUGGEST_DATA is None:
        path = Path(__file__).with_name("suggest_rules.yaml")
        if path.exists():
            try:
                _SUGGEST_DATA = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                _SUGGEST_DATA = {}
        else:
            _SUGGEST_DATA = {}
    return _SUGGEST_DATA


def build_edits(text: str, findings: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    """Build minimal text edit operations for provided findings.

    For the first finding that has a ``suggest_text`` entry in the YAML database for
    the requested ``mode``, a single edit operation is returned. If the finding
    specifies a valid span it becomes a ``replace`` operation; otherwise the
    suggestion is inserted at the end of the text.
    """

    data = _load_suggest_data()
    for f in findings or []:
        code = str(f.get("code", ""))
        cfg = data.get(code, {}) if isinstance(data, dict) else {}
        suggest_text = ((cfg.get("suggest_text") or {}) if isinstance(cfg, dict) else {}).get(mode)
        if not suggest_text:
            continue
        advice = cfg.get("advice") if isinstance(cfg, dict) else None
        span = f.get("span") if isinstance(f, dict) else None
        start = int(span.get("start") or 0) if isinstance(span, dict) else 0
        length = int(span.get("length") or 0) if isinstance(span, dict) else 0
        if not span or length <= 0:
            start = end = len(text or "")
            op = "insert"
        else:
            end = max(start, start + length)
            start = max(0, min(start, len(text)))
            end = max(start, min(end, len(text)))
            op = "replace"
        return [
            {
                "op": op,
                "start": start,
                "end": end,
                "text": suggest_text,
                "comment": advice or "",
            }
        ]
    return []


def compose_paragraph(text: str, findings: List[Dict[str, Any]], mode: str) -> str:
    """Compose a deterministic paragraph using suggested texts for findings."""
    data = _load_suggest_data()
    parts: List[str] = []
    for f in findings or []:
        code = str(f.get("code", ""))
        cfg = data.get(code, {}) if isinstance(data, dict) else {}
        st = ((cfg.get("suggest_text") or {}) if isinstance(cfg, dict) else {}).get(mode)
        if st:
            parts.append(str(st))
    if parts:
        return " ".join(parts)
    return text.strip() if isinstance(text, str) and text.strip() else ""


__all__ = ["build_edits", "compose_paragraph"]
