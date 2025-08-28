"""legal_rules.py — dispatcher/normalizers + registry helpers (fixed)."""

from __future__ import annotations
from typing import Any, Dict, List, Union, Iterable, TYPE_CHECKING

# ✅ Правильний імпорт реєстру (root)
from contract_review_app.legal_rules import registry

if TYPE_CHECKING:
    from contract_review_app.core.schemas import (
        AnalysisInput,
        AnalysisOutput,
        Finding,
        Diagnostic,
        Suggestion,
        Citation,
    )
else:  # pragma: no cover
    try:
        from contract_review_app.core.schemas import (
            AnalysisInput,
            AnalysisOutput,
            Finding,
            Diagnostic,
            Suggestion,
            Citation,
        )
    except Exception:  # pragma: no cover

        class AnalysisInput(dict):
            pass

        class AnalysisOutput(dict):
            pass

        class Finding(dict):
            pass

        class Diagnostic(dict):
            pass

        class Suggestion(dict):
            pass

        class Citation(dict):
            pass


def list_rule_names() -> List[str]:
    """
    Стабільний список доступних правил з root-реєстру.
    """
    try:
        names = list(registry.get_rules_map().keys())
    except Exception:
        names = []
    return sorted(str(n).strip().lower() for n in names)


def normalize_clause_type(val: str, allowed: Iterable[str] | None = None) -> str | None:
    v = (val or "").strip().lower()
    synonyms = {
        "governing law": "governing_law",
        "choice of law": "governing_law",
        "non-disclosure": "confidentiality",
        "non disclosure": "confidentiality",
        "nda": "confidentiality",
        "jurisdiction clause": "jurisdiction",
    }
    v = synonyms.get(v, v)
    pool = set(a.lower() for a in (allowed or list_rule_names()))
    return v if v in pool else None


_ALLOWED_SEVERITIES = {"info", "minor", "major", "critical"}


def _coerce_severity(val: Any) -> str:
    s = str(val or "").strip().lower()
    mapping = {
        "low": "minor",
        "medium": "major",
        "high": "critical",
        "warn": "minor",
        "warning": "minor",
        "error": "critical",
        "fatal": "critical",
        "sev1": "critical",
        "sev2": "major",
        "sev3": "minor",
        "sev0": "info",
    }
    s2 = mapping.get(s, s)
    return s2 if s2 in _ALLOWED_SEVERITIES else "minor"


def _coerce_citations(obj: Any) -> List[Citation]:
    """Normalize citations into a list of Citation objects."""
    if obj is None:
        return []
    items = obj if isinstance(obj, list) else [obj]
    out: List[Citation] = []
    for it in items:
        try:
            if it is None:
                continue
            if isinstance(it, Citation):
                out.append(it)
                continue
            if isinstance(it, str):
                out.append(Citation(instrument=it, section="", system="UK"))
                continue
            if isinstance(it, dict):
                system = it.get("system", "UK")
                instrument = (
                    it.get("instrument") or it.get("title") or it.get("source") or ""
                )
                section = it.get("section", "")
                url = it.get("url") or it.get("link")
                data: Dict[str, Any] = {
                    "system": system,
                    "instrument": str(instrument),
                    "section": str(section),
                }
                if url:
                    data["url"] = url
                score = it.get("score")
                if score is not None:
                    try:
                        s = float(score)
                        if s < 0:
                            s = 0.0
                        elif s > 1:
                            s = 1.0
                        data["score"] = s
                    except Exception:
                        pass
                evidence_text = it.get("evidence_text")
                if evidence_text is not None:
                    data["evidence_text"] = evidence_text
                out.append(Citation(**data))
                continue
        except Exception:
            continue
    return out


def _normalize_findings(raw: Union[None, List[Any]]) -> List[Finding]:
    if not raw:
        return []
    out: List[Finding] = []
    for it in raw:
        try:
            if isinstance(it, Finding):
                sev = _coerce_severity(
                    getattr(it, "severity", getattr(it, "severity_level", None))
                )
                out.append(
                    Finding(
                        code=getattr(it, "code", ""),
                        message=getattr(it, "message", ""),
                        severity=sev,
                        evidence=getattr(it, "evidence", None),
                        span=getattr(it, "span", None),
                        citations=_coerce_citations(getattr(it, "citations", [])),
                        tags=getattr(it, "tags", []),
                        legal_basis=getattr(it, "legal_basis", []),
                    )
                )
            elif isinstance(it, dict):
                d = dict(it)
                d["severity"] = _coerce_severity(
                    d.get("severity", d.get("severity_level"))
                )
                d["citations"] = _coerce_citations(d.get("citations"))
                out.append(Finding(**d))
            else:
                out.append(Finding(code="GEN", message=str(it), severity="minor"))
        except Exception:
            out.append(Finding(code="GEN_ERR", message=str(it), severity="minor"))
    return out


def _normalize_diagnostics(raw: Union[None, List[Any]]) -> List[Diagnostic]:
    if not raw:
        return []
    out: List[Diagnostic] = []
    for item in raw:
        if isinstance(item, Diagnostic):
            out.append(item)
        elif isinstance(item, str):
            out.append(Diagnostic(rule="ENGINE", message=item, severity="info"))
        elif isinstance(item, dict):
            out.append(
                Diagnostic(
                    rule=str(item.get("rule", "ENGINE")),
                    message=str(item.get("message", "")),
                    severity=item.get("severity", "info"),
                    legal_basis=item.get("legal_basis", []),
                )
            )
        else:
            out.append(Diagnostic(rule="ENGINE", message=str(item), severity="info"))
    return out


def _normalize_suggestions(raw: Union[None, List[Any]]) -> List[Suggestion]:
    if not raw:
        return []
    out: List[Suggestion] = []
    for item in raw:
        if isinstance(item, Suggestion):
            out.append(item)
        elif isinstance(item, str):
            out.append(Suggestion(text=item))
        elif isinstance(item, dict):
            msg = item.get("text", item.get("message", ""))
            out.append(Suggestion(text=str(msg), reason=item.get("reason")))
        else:
            out.append(Suggestion(text=str(item)))
    return out


def _map_status(val: str) -> str:
    v = (val or "").strip().upper()
    if v in {"✅", "OK", "PASS"}:
        return "OK"
    if v in {"⚠️", "WARN", "WARNING"}:
        return "WARN"
    if v in {"❌", "FAIL", "ERROR"}:
        return "FAIL"
    return "WARN"


def default_checker(input_data: AnalysisInput) -> AnalysisOutput:
    fallback_findings = _normalize_findings(
        [
            {
                "code": "RULE_NOT_IMPLEMENTED",
                "message": f"No rule implemented for clause type: {getattr(input_data,'clause_type',None)}",
                "severity": "minor",
            }
        ]
    )
    return AnalysisOutput(
        clause_type=getattr(input_data, "clause_type", None),
        text=getattr(input_data, "text", None),
        status="WARN",
        findings=fallback_findings,
        diagnostics=_normalize_diagnostics(["Default rule fallback used."]),
        trace=["Fallback to default_checker()"],
        clause_name=(
            (getattr(input_data, "metadata", {}) or {}).get("name", "")
            if hasattr(input_data, "metadata")
            else ""
        ),
        category="Unknown",
        score=50,
        risk_level="medium",
        severity="medium",
    )


def analyze(input_data: AnalysisInput) -> AnalysisOutput:
    # 🔄 Гарантовано підвантажити правила перед диспетчеризацією
    try:
        registry.discover_rules()  # якщо доступно у root-реєстрі
    except Exception:
        pass
    rules_map = registry.get_rules_map()

    trace = [f"analyze(): clause_type = {getattr(input_data,'clause_type',None)!r}"]
    clause_type_raw = getattr(input_data, "clause_type", "") or ""
    clause_type_norm = normalize_clause_type(clause_type_raw)

    if clause_type_norm and clause_type_norm in rules_map:
        checker_fn = rules_map[clause_type_norm]
        trace.append(f"Matched rule: {checker_fn.__name__}")
        result = checker_fn(input_data)

        if isinstance(result, dict):
            diagnostics = _normalize_diagnostics(result.get("diagnostics", []))
            suggestions = _normalize_suggestions(result.get("suggestions", []))
            rule_trace = result.get("trace", [])
            trace_final = trace + (rule_trace if isinstance(rule_trace, list) else [])
            recs = result.get("recommendations", [])
            if isinstance(recs, str):
                recs = [recs]
            elif not isinstance(recs, list):
                recs = []
            legacy_rec = result.get("recommendation")
            if isinstance(legacy_rec, str) and legacy_rec:
                recs.append(legacy_rec)
            citations = _coerce_citations(result.get("citations"))
            findings_norm = _normalize_findings(result.get("findings", []))
            return AnalysisOutput(
                clause_type=clause_type_norm,
                text=(
                    getattr(input_data, "text", "")
                    if hasattr(input_data, "text")
                    else ""
                ),
                status=_map_status(result.get("status", "WARN")),
                score=result.get("score", 50),
                risk_level=result.get("risk_level", "medium"),
                severity=result.get("severity", "medium"),
                findings=findings_norm,
                recommendations=recs,
                diagnostics=diagnostics,
                suggestions=suggestions,
                trace=trace_final,
                citations=citations,
                category=result.get("issue_type", "general"),
                clause_name=(
                    input_data.metadata.get("name", "")
                    if hasattr(input_data, "metadata")
                    else ""
                ),
            )

        if isinstance(result, AnalysisOutput):
            try:
                result.trace.insert(0, f"Rule matched for: {clause_type_norm}")
                result.diagnostics = _normalize_diagnostics(result.diagnostics)
                result.suggestions = _normalize_suggestions(result.suggestions)
                result.findings = _normalize_findings(result.findings)
            except Exception:
                pass
            result.trace = trace + (result.trace if hasattr(result, "trace") else [])
            return result

        fb = default_checker(input_data)
        fb.diagnostics = _normalize_diagnostics(
            [
                {
                    "rule": "ENGINE",
                    "message": f"Unexpected rule result type: {type(result)}",
                    "severity": "warning",
                }
            ]
        )
        fb.trace = trace + fb.trace
        return fb

    trace.append(f"No rule found for '{clause_type_raw}', using default_checker")
    result = default_checker(input_data)
    result.trace = trace + result.trace
    return result


__all__ = [
    "list_rule_names",
    "normalize_clause_type",
    "default_checker",
    "analyze",
]
