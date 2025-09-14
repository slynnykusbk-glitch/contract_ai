# contract_review_app/engine/executor.py
from __future__ import annotations

from time import monotonic
from typing import Dict, List, Optional

from loguru import logger

from contract_review_app.core.schemas import (
    AnalysisInput,
    AnalysisOutput,
    DocIndex,
    Finding,
    Span,
    risk_to_ord,
    ord_to_risk,
)
from contract_review_app.engine.intake import segment_document
from contract_review_app.legal_rules.registry import run_rule, get_rules_map

# optional legacy .docx loader
try:
    from contract_review_app.utils.doc_loader import load_docx_text  # type: ignore
except Exception:  # pragma: no cover
    load_docx_text = None  # type: ignore

# optional cross-checks
try:
    from contract_review_app.legal_rules.cross_checks import cross_check_clauses  # type: ignore
except Exception:  # pragma: no cover

    def cross_check_clauses(inputs, outputs):  # type: ignore
        return outputs


# deterministic scoring weights per finding severity
_SEV_WEIGHT = {
    "info": 1,
    "minor": 10,
    "major": 25,
    "critical": 50,
}


def _coerce_span(v) -> Span:
    """
    Accept Span | dict | None -> Span (non-negative, length>=0).
    """
    if v is None:
        return Span(start=0, length=0)
    if isinstance(v, Span):
        return v
    # dict or other -> try to coerce
    try:
        start = int(
            getattr(v, "start", None) if hasattr(v, "start") else v.get("start", 0)
        )
        length = int(
            getattr(v, "length", None) if hasattr(v, "length") else v.get("length", 0)
        )
        if start < 0:
            start = 0
        if length < 0:
            length = 0
        return Span(start=start, length=length)
    except Exception:
        return Span(start=0, length=0)


def _ensure_abs_spans(
    out: AnalysisOutput, clause_span_start: int, clause_text_len: int
) -> None:
    """
    Make every finding's span absolute (document coords). If missing, pin to clause span.
    """
    try:
        for f in out.findings or []:
            sp = _coerce_span(getattr(f, "span", None))
            if sp.length == 0:
                # no local span -> pin to whole clause
                f.span = Span(start=int(clause_span_start), length=int(clause_text_len))
            else:
                # local (relative to clause) -> convert to absolute
                f.span = Span(
                    start=int(clause_span_start) + int(sp.start), length=int(sp.length)
                )
    except Exception:
        # do not fail the pipeline
        pass


def _compute_clause_metrics(out: AnalysisOutput) -> None:
    """
    Deterministic risk/status/score for a clause based on its findings.
    - risk: max ordinal of finding risks (fallback medium)
    - status: critical -> FAIL; high/major -> WARN; else OK
    - score: 100 - sum(weights); clamped to [0..100]
    """
    findings: List[Finding] = list(out.findings or [])
    # risk (max by ordinal)
    max_ord = 1  # medium by default
    for f in findings:
        r = getattr(f, "risk", None)
        if not r and getattr(f, "severity_level", None):
            # severity->risk fallback is handled in Finding, but keep defensive
            sev = str(f.severity_level)
            r = {
                "info": "low",
                "minor": "medium",
                "major": "high",
                "critical": "critical",
            }.get(sev, "medium")
        max_ord = max(max_ord, risk_to_ord(r or "medium"))
    out.risk = ord_to_risk(max_ord)

    # status
    has_critical = any(
        getattr(f, "severity_level", None) == "critical" for f in findings
    )
    has_major_or_high = any(
        getattr(f, "severity_level", None) == "major"
        or (getattr(f, "risk", None) == "high")
        for f in findings
    )
    if has_critical:
        out.status = "FAIL"
    elif has_major_or_high:
        out.status = "WARN"
    else:
        out.status = "OK"

    # score
    total = 0
    for f in findings:
        w = _SEV_WEIGHT.get(str(getattr(f, "severity_level", "minor")), 10)
        total += w
    score = max(0, min(100, 100 - total))
    out.score = int(score)

    # legacy textual fields (compat layer)
    out.risk_level = str(out.risk)
    out.severity = (
        "high"
        if out.risk in ("high", "critical")
        else ("medium" if out.risk == "medium" else "low")
    )


def analyze_index_with_rules(
    index: DocIndex,
    jurisdiction: str = "UK",
    policy_pack: Optional[dict] = None,
    timeout_ms: Optional[int] = 20,
) -> List[AnalysisOutput]:
    """
    Deterministic rule execution over segmented clauses.
    - single safe runner via rules.registry.run_rule (timeout + circuit breaker)
    - absolute spans for all findings
    - trace/diagnostics with elapsed time per rule
    - deterministic risk/status/score per clause
    - post-pass cross-checks
    """
    # ensure discovery; we never use raw registry maps directly
    _ = get_rules_map()

    outputs: List[AnalysisOutput] = []
    inputs: List[AnalysisInput] = []

    ordered = list(getattr(index, "clauses", []) or [])
    for i, clause in enumerate(ordered):
        clause_type = (
            getattr(clause, "type", None) or getattr(clause, "clause_type", None) or ""
        ).lower()
        if not clause_type:
            continue

        neighbors = {
            "prev": getattr(ordered[i - 1], "text", "") if i > 0 else "",
            "next": getattr(ordered[i + 1], "text", "") if i + 1 < len(ordered) else "",
        }

        span_obj = getattr(clause, "span", None)
        span_start = int(getattr(span_obj, "start", 0) if span_obj is not None else 0)
        clause_text = getattr(clause, "text", "") or ""
        meta = {
            "name": getattr(clause, "title", "") or clause_type,
            "span_start": span_start,
            "neighbors": neighbors,
            "jurisdiction": jurisdiction,
            "policy_pack": dict(policy_pack or {}),
        }
        if timeout_ms is not None:
            meta["timeout_ms"] = int(timeout_ms)

        inp = AnalysisInput(clause_type=clause_type, text=clause_text, metadata=meta)
        inputs.append(inp)

        t0 = monotonic()
        out = run_rule(clause_type, inp)
        elapsed_ms = int((monotonic() - t0) * 1000)

        # ensure absolute spans
        _ensure_abs_spans(out, span_start, len(clause_text))

        # enrich diagnostics/trace
        try:
            out.trace = list((out.trace or [])) + [
                f"rule:{clause_type}",
                f"elapsed_ms:{elapsed_ms}",
            ]
            out.diagnostics = list((out.diagnostics or [])) + [
                f"runner: {clause_type} in {elapsed_ms}ms"
            ]
        except Exception:
            pass

        # deterministic metrics
        _compute_clause_metrics(out)

        outputs.append(out)

    # post-pass cross checks (do not mutate inputs)
    try:
        outputs = cross_check_clauses(inputs, outputs) or outputs
    except Exception as e:
        logger.warning("cross_check_clauses failed: {!r}", e)

    # ensure spans still absolute after cross-checks
    try:
        for i, clause in enumerate(ordered):
            span_obj = getattr(clause, "span", None)
            span_start = int(
                getattr(span_obj, "start", 0) if span_obj is not None else 0
            )
            clause_text = getattr(clause, "text", "") or ""
            _ensure_abs_spans(outputs[i], span_start, len(clause_text))
            _compute_clause_metrics(outputs[i])  # re-evaluate if CC changed findings
    except Exception:
        pass

    return outputs


# -------- Legacy convenience (kept for backward compatibility) --------
def analyze_document(file_path: str) -> Dict[str, AnalysisOutput]:
    """
    Legacy wrapper: load .docx -> segment -> run rules.
    Returns a dict keyed by clause_type for convenience.
    Prefer using pipeline.analyze_document(text) for SSOT response.
    """
    if not load_docx_text:
        raise RuntimeError(
            "doc_loader is not available; use pipeline.analyze_document(text) instead."
        )
    text = load_docx_text(file_path)
    index = segment_document(text)
    outs = analyze_index_with_rules(index=index)
    final: Dict[str, AnalysisOutput] = {}
    for o in outs:
        try:
            final[str(o.clause_type)] = o
        except Exception:
            pass
    return final
