import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml

# Load templates from YAML
_TEMPLATES_PATH = Path(__file__).with_name("suggest_templates.yaml")
try:
    with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        _TEMPLATES = yaml.safe_load(f) or {}
except Exception:
    _TEMPLATES = {}


def _ensure_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def suggest_edits(text: str, clause_type: Optional[str] = None, span: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Return actionable edits for a clause.

    Args:
        text: Clause text.
        clause_type: Optional clause type key.
        span: Optional dict with start/length if text is part of a bigger document.

    Returns:
        Dict with keys ``edits`` and ``meta``.
    """
    text = text or ""
    template = _TEMPLATES.get(clause_type or "") if clause_type else None
    if not template:
        return {"edits": [], "meta": {"reason": "unknown_clause_type"}}

    edits: List[Dict[str, Any]] = []
    tmpl_edits = template.get("edits", [])
    for e in tmpl_edits:
        action = e.get("action", "insert_if_missing")
        note = _ensure_str(e.get("note"))
        replacement = _ensure_str(e.get("replacement"))
        if action == "replace":
            start = span.get("start", 0) if span else 0
            length = span.get("length", len(text)) if span else len(text)
            edits.append({"range": {"start": int(start), "length": int(length)}, "replacement": replacement, "note": note})
        elif action == "insert_if_missing":
            if replacement not in text:
                start = (span.get("start", 0) + span.get("length", 0)) if span else len(text)
                edits.append({"range": {"start": int(start), "length": 0}, "replacement": replacement, "note": note})
        elif action == "replace_pattern":
            pattern = e.get("pattern")
            if not isinstance(pattern, str):
                continue
            for m in re.finditer(pattern, text):
                start = m.start()
                length = m.end() - m.start()
                edits.append({"range": {"start": int(start), "length": int(length)}, "replacement": replacement, "note": note})
    meta = {"clause_type": clause_type or ""}
    if not edits:
        meta["reason"] = "no_match"
    return {"edits": edits, "meta": meta}
