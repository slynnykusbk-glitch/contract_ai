"""Lightweight YAML rule loader and matcher."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

# ---------------------------------------------------------------------------
# Load and compile rules on import
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = []
# additional python-level rules with custom validators
_PY_RULES: List[Dict[str, Any]] = []


def _load_rules() -> None:
    base = Path(__file__).resolve().parent / "policy_packs"
    if not base.exists():
        return
    for path in base.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for raw in data.get("rules") or []:
            pats = [re.compile(p) for p in raw.get("patterns", [])]
            _RULES.append(
                {
                    "id": raw.get("id"),
                    "clause_type": raw.get("clause_type"),
                    "severity": raw.get("severity"),
                    "patterns": pats,
                    "advice": raw.get("advice"),
                }
            )


_load_rules()

# ---------------------------------------------------------------------------
# Common regex helpers
# ---------------------------------------------------------------------------
MONEY_RX = re.compile(
    r"(?:(£|€|\$)\s*|\b(GBP|EUR|USD)\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
    re.IGNORECASE,
)
PERCENT_RX = re.compile(r"\b\d+(?:\.\d+)?%")


def _to_number(val: str) -> float:
    """Convert currency/percentage string to numeric value."""
    try:
        return float(val.replace(",", ""))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Numeric rule implementations
# ---------------------------------------------------------------------------
def _rule_insurance_limits(text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    checks = [
        (r"employers'? liability", 10_000_000),
        (r"public liability", 5_000_000),
    ]
    # professional indemnity only if professional services mentioned
    if re.search(r"professional services", text, re.IGNORECASE):
        checks.append((r"professional indemnity", 2_000_000))
    for label, minimum in checks:
        rx = re.compile(label + r"[^£€$\d]{0,50}" + MONEY_RX.pattern, re.IGNORECASE)
        m = rx.search(text)
        if not m:
            findings.append(
                {
                    "rule_id": "insurance_limits_min",
                    "clause_type": "insurance",
                    "severity": "high",
                    "start": 0,
                    "end": 0,
                    "snippet": f"Missing {label} amount",
                    "advice": f"Specify at least £{minimum:,} for {label}.",
                }
            )
            continue
        amount_str = m.group(3)
        amount = _to_number(amount_str)
        if amount < minimum:
            findings.append(
                {
                    "rule_id": "insurance_limits_min",
                    "clause_type": "insurance",
                    "severity": "high",
                    "start": m.start(3),
                    "end": m.end(3),
                    "snippet": m.group(0),
                    "advice": f"Increase {label} to at least £{minimum:,}.",
                }
            )
    return findings


def _rule_cap_present(keyword: str, rule_id: str, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if re.search(keyword, text, re.IGNORECASE):
        rx = re.compile(keyword + r"[^£€$\d]{0,50}" + MONEY_RX.pattern, re.IGNORECASE)
        m = rx.search(text)
        if not m or re.search(r"xx|tbd|to be", m.group(0), re.IGNORECASE):
            findings.append(
                {
                    "rule_id": rule_id,
                    "clause_type": "liability_cap",
                    "severity": "medium",
                    "start": m.start() if m else 0,
                    "end": m.end() if m else 0,
                    "snippet": m.group(0) if m else keyword,
                    "advice": "Provide a concrete monetary cap",
                }
            )
    return findings


def _rule_pollution_cap(text: str) -> List[Dict[str, Any]]:
    return _rule_cap_present(r"pollution", "pollution_cap_present", text)


def _rule_property_damage_cap(text: str) -> List[Dict[str, Any]]:
    return _rule_cap_present(r"property damage", "property_damage_cap_present", text)


def _rule_service_credits(text: str) -> List[Dict[str, Any]]:
    if re.search(r"\bSLA\b|service level agreement", text, re.IGNORECASE):
        if not re.search(r"service credits|liquidated damages", text, re.IGNORECASE):
            return [
                {
                    "rule_id": "service_credits_lds_present_if_sla",
                    "clause_type": "service_levels",
                    "severity": "medium",
                    "start": 0,
                    "end": 0,
                    "snippet": "SLA referenced without service credits/LDs",
                    "advice": "Include service credits or liquidated damages when referencing an SLA",
                }
            ]
    return []


def _rule_payment_terms(text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    m = re.search(r"net\s*(\d{1,3})\s*days", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        if not (30 <= days <= 45):
            findings.append(
                {
                    "rule_id": "payment_terms_days",
                    "clause_type": "payment_terms",
                    "severity": "medium",
                    "start": m.start(1),
                    "end": m.end(1),
                    "snippet": m.group(0),
                    "advice": "Payment terms should be within 30-45 days",
                }
            )
    else:
        findings.append(
            {
                "rule_id": "payment_terms_days",
                "clause_type": "payment_terms",
                "severity": "medium",
                "start": 0,
                "end": 0,
                "snippet": "Payment term not found",
                "advice": "Specify net payment days",
            }
        )
    if not re.search(r"valid\s+VAT\s+invoice", text, re.IGNORECASE):
        findings.append(
            {
                "rule_id": "payment_terms_days",
                "clause_type": "payment_terms",
                "severity": "medium",
                "start": 0,
                "end": 0,
                "snippet": "VAT invoice requirement missing",
                "advice": "Require a valid VAT invoice",
            }
        )
    return findings


_PY_RULES.extend(
    [
        _rule_insurance_limits,
        _rule_pollution_cap,
        _rule_property_damage_cap,
        _rule_service_credits,
        _rule_payment_terms,
    ]
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def discover_rules() -> List[Dict[str, Any]]:
    """Return loaded rules without compiled regex objects."""
    out: List[Dict[str, Any]] = []
    for r in _RULES:
        out.append(
            {
                "id": r.get("id"),
                "clause_type": r.get("clause_type"),
                "severity": r.get("severity"),
                "patterns": [p.pattern for p in r.get("patterns", [])],
                "advice": r.get("advice"),
            }
        )
    return out


def rules_count() -> int:
    """Return the number of loaded rules."""
    return len(_RULES) + len(_PY_RULES)


def match_text(text: str) -> List[Dict[str, Any]]:
    """Match text against loaded rules and return findings."""
    findings: List[Dict[str, Any]] = []
    if not text:
        return findings
    for r in _RULES:
        for pat in r.get("patterns", []):
            for m in pat.finditer(text):
                findings.append(
                    {
                        "rule_id": r.get("id"),
                        "clause_type": r.get("clause_type"),
                        "severity": r.get("severity"),
                        "start": m.start(),
                        "end": m.end(),
                        "snippet": text[m.start() : m.end()],
                        "advice": r.get("advice"),
                    }
                )
    for func in _PY_RULES:
        try:
            findings.extend(func(text))
        except Exception:
            continue
    return findings

