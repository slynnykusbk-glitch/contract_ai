from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

# Load templates from YAML
_TEMPLATES_PATH = Path(__file__).with_name("suggest_templates.yaml")
try:
    _TEMPLATES: Dict[str, Dict[str, Any]] = yaml.safe_load(_TEMPLATES_PATH.read_text()) or {}
except FileNotFoundError:  # pragma: no cover
    _TEMPLATES = {}


def _range_from_findings(text: str, findings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
    """Compute replacement range using first finding span if available."""
    if findings:
        for f in findings:
            span = f.get("span") if isinstance(f, dict) else getattr(f, "span", None)
            if isinstance(span, dict):
                start = int(span.get("start", 0))
                end = int(span.get("end", start))
                if end > start:
                    return {"start": start, "length": end - start}
    return {"start": 0, "length": len(text or "")}


# Map clause types to range functions; default uses finding spans
_RANGE_FUNCS: Dict[str, Callable[[str, Optional[List[Dict[str, Any]]]], Dict[str, int]]] = {
    ct: _range_from_findings for ct in _TEMPLATES.keys()
}


def has_template(clause_type: str) -> bool:
    """Return True if templates exist for the clause type."""
    return clause_type in _TEMPLATES


def suggest_for_clause(
    text: str,
    clause_type: str,
    profile: str = "friendly",
    findings: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build suggestion cards for a given clause type."""
    info = _TEMPLATES.get(clause_type)
    if not info:
        return []

    template = ""
    st = info.get("suggest_text") if isinstance(info, dict) else None
    if isinstance(st, dict):
        template = st.get(profile) or st.get("friendly") or st.get("default") or ""
    if not template:
        edits = info.get("edits") if isinstance(info, dict) else None
        if isinstance(edits, list) and edits:
            template = edits[0].get("template", "")
    template = str(template)
    note = str(info.get("note", ""))

    rng = _RANGE_FUNCS.get(clause_type, _range_from_findings)(text or "", findings)
    action = "replace" if rng.get("length", 0) > 0 else "append"

    return [
        {
            "clause_type": clause_type,
            "action": action,
            "range": rng,
            "proposed_text": template,
            "message": template,
            "note": note,
        }
    ]
