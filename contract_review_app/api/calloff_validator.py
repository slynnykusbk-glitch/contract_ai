from __future__ import annotations
"""Simple rule-based validator for Call-Off details."""

from typing import Any, Dict, List
import re

REQUIRED_FIELDS = {
    "term": "Term",
    "description": "Services/Goods description",
    "price": "Price",
    "currency": "Currency",
    "vat": "VAT",
    "delivery_point": "Delivery Point",
    "representatives": "Representatives address",
    "notices": "Notices address",
    "po_number": "PO/Call-Off number",
}

_PLACEHOLDER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (r"\[●\]", r"TBC")]

def _has_placeholder(val: str) -> bool:
    for pat in _PLACEHOLDER_PATTERNS:
        if pat.search(val):
            return True
    return False

def validate_calloff(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []

    # required fields
    for key, label in REQUIRED_FIELDS.items():
        val = data.get(key)
        if not isinstance(val, str) or not val.strip():
            issues.append({
                "id": "calloff_required_fields",
                "severity": "major",
                "advice": f"{label} is required",
                "location": key,
            })

    # placeholders in any string or list of strings
    def check_placeholder(field: str, value: Any) -> None:
        if isinstance(value, str):
            if _has_placeholder(value):
                issues.append({
                    "id": "calloff_placeholders_forbidden",
                    "severity": "major",
                    "advice": f"Placeholder detected in {field}",
                    "location": field,
                })
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                check_placeholder(f"{field}[{idx}]", item)

    for k, v in data.items():
        check_placeholder(k, v)

    # subcontractor listing
    uses_sub = bool(data.get("subcontracts") or data.get("uses_subcontracts"))
    subs = data.get("subcontractors") or data.get("critical_subcontractors")
    if uses_sub and (not isinstance(subs, list) or len(subs) == 0):
        issues.append({
            "id": "calloff_subcontractor_listing",
            "severity": "major",
            "advice": "List critical subcontractors when subcontracts are used",
            "location": "subcontractors",
        })

    # variation link
    if data.get("scope_altered") and not data.get("variation_reference"):
        issues.append({
            "id": "calloff_variation_link",
            "severity": "major",
            "advice": "Provide VO/VR reference when scope is altered",
            "location": "variation_reference",
        })

    return issues
