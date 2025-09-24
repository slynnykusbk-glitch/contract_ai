# contract_review_app/legal_rules/runner.py
from __future__ import annotations

from typing import List, Tuple, Optional

from core.schemas import Finding, Citation
from contract_review_app.legal_rules.registry import get_checker_for_clause


def run_rule_for_clause(
    clause_type: str,
    text: str,
    span_start: int,
    neighbors: Optional[dict] = None,
    jurisdiction: str = "UK",
    policy_pack: Optional[dict] = None,
    timeout_ms: Optional[int] = None,
) -> Tuple[List[Finding], Optional[str], List[Citation]]:
    """
    Execute a single rule with a unified ctx and per-rule timeout (handled by wrapper).
    Never raises; returns empty sets on failure/timeout.
    """
    checker = get_checker_for_clause(clause_type)
    if not checker:
        return [], None, []
    ctx = {
        "clause_type": clause_type,
        "span_start": int(span_start or 0),
        "neighbors": dict(neighbors or {}),
        "jurisdiction": jurisdiction,
        "policy_pack": dict(policy_pack or {}),
    }
    if timeout_ms is not None:
        ctx["timeout_ms"] = int(timeout_ms)
    try:
        return checker(text or "", ctx)
    except Exception:
        return [], None, []
