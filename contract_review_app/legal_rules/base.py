from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Union, Dict, List, Optional

from contract_review_app.core.schemas import AnalysisOutput, Finding

# ---- Severity → ваги для score ------------------------------------------------


class Severity(Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


_SEV_WEIGHTS = {
    Severity.CRITICAL: -30,
    Severity.MAJOR: -20,
    Severity.MINOR: -10,
}
_STR_WEIGHTS = {
    "critical": -30,
    "high": -30,
    "major": -20,
    "medium": -20,
    "warning": -20,
    "warn": -20,
    "minor": -10,
    "low": -10,
    "info": 0,
    None: 0,
}

# ---- Нормалізація findings ----------------------------------------------------


def _citations_str(val):
    if isinstance(val, list):
        return "; ".join(str(x) for x in val)
    if val is None:
        return ""
    return str(val)


def _coerce_finding(item: Any) -> Optional[Finding]:
    """
    Приймає dict/строку/Finding і повертає Finding.
    - str → message (code='GENERIC')
    - dict → мапить code/message/severity/evidence/legal_basis
    - Finding → як є
    """
    if item is None:
        return None
    if isinstance(item, Finding):
        return item
    if isinstance(item, str):
        return Finding(code="GENERIC", message=item)
    if isinstance(item, dict):
        return Finding(
            code=item.get("code") or "GENERIC",
            message=item.get("message") or "",
            severity=(
                str(item.get("severity")).lower()
                if item.get("severity") is not None
                else None
            ),
            evidence=item.get("evidence"),
            legal_basis=item.get("legal_basis") or [],
        )
    # інші типи ігноруємо
    return None


def _coerce_findings(
    items: Iterable[Union[Severity, Dict[str, Any], str, Finding]],
) -> List[Finding]:
    out: List[Finding] = []
    for it in items or []:
        f = _coerce_finding(it)
        if f:
            out.append(f)
    return out


# ---- Обчислення score ---------------------------------------------------------


def _weight(item: Any) -> int:
    """
    Витягає вагу з:
    - Severity enum
    - рядка ("high"/"medium"/"low"/"info")
    - dict/Finding -> .severity
    """
    if isinstance(item, Severity):
        return _SEV_WEIGHTS.get(item, 0)
    if isinstance(item, Finding):
        return _STR_WEIGHTS.get((item.severity or "").lower() or None, 0)
    if isinstance(item, str):
        return _STR_WEIGHTS.get(item.lower(), 0)
    if isinstance(item, dict):
        sev = item.get("severity")
        if isinstance(sev, Severity):
            return _SEV_WEIGHTS.get(sev, 0)
        if isinstance(sev, str):
            return _STR_WEIGHTS.get(sev.lower(), 0)
    return 0


def score_from_findings(
    findings: Iterable[Union[Severity, Dict[str, Any], str, Finding]],
) -> int:
    score = 100
    for it in findings or []:
        score += _weight(it)
    # clamp
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score


# ---- Фабрики результатів ------------------------------------------------------


def _make_output(
    status: str,
    *,
    findings=None,
    problems=None,
    recommendations=None,
    legal_basis=None,
    trace=None,
    clause_type=None,
    text=None,
    diagnostics=None,
) -> AnalysisOutput:
    findings = _coerce_findings(findings or [])
    problems = list(problems or [])
    recommendations = list(recommendations or [])
    legal_basis = list(legal_basis or [])
    trace = list(trace or [])
    diagnostics = dict(diagnostics or {})

    return AnalysisOutput(
        clause_type=clause_type,
        text=text,
        status=status,  # type: ignore
        score=score_from_findings(findings),
        findings=findings,
        problems=problems,
        recommendations=recommendations,
        legal_basis=legal_basis,
        trace=trace,
        diagnostics=diagnostics,
    )


def ok(**kwargs) -> AnalysisOutput:
    return _make_output("OK", **kwargs)


def warn(**kwargs) -> AnalysisOutput:
    return _make_output("WARN", **kwargs)


def fail(**kwargs) -> AnalysisOutput:
    return _make_output("FAIL", **kwargs)
