from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
import hashlib

from .doc_type import guess_doc_type, slug_to_display
from contract_review_app.engine.pipeline_compat import (
    map_norm_span_to_raw,
    normalized_view,
)
from contract_review_app.core.citation_resolver import resolve_citation

# Keep schema types for compatibility (DocumentAnalysis return, Clause/Span shapes, etc.)
try:
    from contract_review_app.core.schemas import (  # type: ignore
        AnalysisInput,
        AnalysisOutput,
        Clause,
        CrossRef,
        DocIndex,
        DocumentAnalysis,
        DraftMode,
        Finding,
        Span,
        risk_to_ord,
        ord_to_risk,
    )
except Exception:
    # Minimal dummies allowing dict-style construction if schemas not present
    class Span(dict):  # type: ignore
        def __init__(self, start: int = 0, length: int = 0, **kw: Any) -> None:
            super().__init__(start=int(start or 0), length=int(length or 0), **kw)
            self.start = int(self["start"])
            self.length = int(self["length"])

    class Clause(dict):  # type: ignore
        def __init__(
            self, id: str, type: str, text: str, span: Span, title: str = ""
        ) -> None:
            super().__init__(id=id, type=type, text=text, span=span, title=title)
            self.id, self.type, self.text, self.span, self.title = (
                id,
                type,
                text,
                span,
                title,
            )

    class DocIndex(dict):  # type: ignore
        def __init__(
            self,
            document_name: Optional[str],
            language: Optional[str],
            clauses: List[Clause],
        ) -> None:
            super().__init__(
                document_name=document_name, language=language, clauses=clauses
            )
            self.document_name, self.language, self.clauses = (
                document_name,
                language,
                clauses,
            )

    class Finding(dict):  # type: ignore
        pass

    class AnalysisOutput(dict):  # type: ignore
        def __init__(self, **kw: Any) -> None:
            super().__init__(**kw)
            for k, v in kw.items():
                setattr(self, k, v)

    class DocumentAnalysis(dict):  # type: ignore
        def __init__(self, **kw: Any) -> None:
            super().__init__(**kw)
            for k, v in kw.items():
                setattr(self, k, v)

    def risk_to_ord(s: str) -> int:  # type: ignore
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(
            (s or "medium").lower(), 1
        )

    def ord_to_risk(i: int) -> str:  # type: ignore
        table = ["low", "medium", "high", "critical"]
        return table[max(0, min(len(table) - 1, int(i or 0)))]

    DraftMode = str  # type: ignore
    AnalysisInput = Any  # type: ignore

# Optional matcher & rules
try:
    from contract_review_app.engine import matcher as _matcher  # type: ignore
except Exception:
    _matcher = None

try:
    from contract_review_app.legal_rules.rules import oilgas_master_agreement as _uk_og_msa  # type: ignore
except Exception:
    _uk_og_msa = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _stable_id_from_span(text_fragment: str, start: int, length: int) -> str:
    h = hashlib.blake2b(digest_size=16)
    h.update(str(start).encode())
    h.update(str(length).encode())
    h.update((text_fragment or "")[:256].encode("utf-8", "ignore"))
    return h.hexdigest()


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _slice(text: str, start: int, length: int) -> str:
    n = len(text or "")
    s = max(0, int(start or 0))
    e = max(s, min(n, s + max(0, int(length or 0))))
    return (text or "")[s:e]


def _norm_span(span_like: Any) -> Span:
    if isinstance(span_like, dict):
        start = int(span_like.get("start", 0) or 0)
        if "length" in span_like:
            length = int(span_like.get("length", 0) or 0)
        else:
            end = int(span_like.get("end", start) or start)
            length = max(0, end - start)
        return Span(start=start, length=max(0, length))
    # fallback
    return Span(start=0, length=0)


def _sections_via_matcher(text: str) -> List[Dict[str, Any]]:
    if _matcher and hasattr(_matcher, "classify_sections"):
        try:
            secs = _matcher.classify_sections(text or "")
            if isinstance(secs, list):
                # Normalize spans
                out: List[Dict[str, Any]] = []
                for s in secs:
                    sp = _norm_span((s or {}).get("span", {}))
                    out.append(
                        {
                            "clause_type": str(
                                (s or {}).get("clause_type") or "unknown"
                            ),
                            "title": str((s or {}).get("title") or ""),
                            "span": {"start": int(sp.start), "length": int(sp.length)},
                        }
                    )
                # stable order: start asc, then clause_type asc
                out.sort(key=lambda d: (int(d["span"]["start"]), d["clause_type"]))
                return out
        except Exception:
            pass
    # Fallback single section (document)
    return [
        {
            "clause_type": "unknown",
            "title": "DOCUMENT",
            "span": {"start": 0, "length": len(text or "")},
        }
    ]


def _rules_evaluate(
    text: str, sections: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if _uk_og_msa and hasattr(_uk_og_msa, "evaluate"):
        try:
            analyses, metrics = _uk_og_msa.evaluate(text or "", sections or [])
            if isinstance(analyses, list) and isinstance(metrics, dict):
                # Normalize each analysis span
                out_analyses: List[Dict[str, Any]] = []
                for a in analyses:
                    aa = dict(a or {})
                    aa["clause_type"] = str(aa.get("clause_type") or "unknown")
                    aa["title"] = str(aa.get("title") or "")
                    aa["risk_level"] = str(
                        aa.get("risk_level") or aa.get("risk") or "medium"
                    )
                    aa["score"] = int(aa.get("score") or 0)
                    aa["span"] = {
                        "start": int(_norm_span(aa.get("span")).start),
                        "length": int(_norm_span(aa.get("span")).length),
                    }
                    # normalize finding spans
                    f_norm: List[Dict[str, Any]] = []
                    for f in aa.get("findings") or []:
                        ff = dict(f or {})
                        ff["span"] = {
                            "start": int(_norm_span(ff.get("span")).start),
                            "length": int(_norm_span(ff.get("span")).length),
                        }
                        f_norm.append(ff)
                    aa["findings"] = f_norm
                    out_analyses.append(aa)
                # stable order
                out_analyses.sort(
                    key=lambda d: (
                        int(d.get("span", {}).get("start", 0)),
                        d.get("clause_type", ""),
                    )
                )
                # Metrics shape
                m = dict(metrics or {})
                m.setdefault("summary_status", "OK")
                m.setdefault("summary_risk", "medium")
                m.setdefault("summary_score", 0)
                return out_analyses, m
        except Exception:
            pass
    # Fallback: neutral metrics, no analyses
    return [], {"summary_status": "OK", "summary_risk": "medium", "summary_score": 0}


def _to_finding_model(f: Dict[str, Any]) -> Any:
    sp = _norm_span(f.get("span", {}))
    try:
        finding = Finding(
            **{
                "code": f.get("code"),
                "message": f.get("message"),
                "severity": f.get("severity"),
                "span": sp,
            }
        )  # type: ignore
    except Exception:
        finding = {
            "code": f.get("code"),
            "message": f.get("message"),
            "severity": f.get("severity"),
            "span": {"start": sp.start, "length": sp.length},
            "citations": [],
        }
    try:
        citation = resolve_citation(finding)
        if citation:
            if isinstance(finding, dict):
                finding.setdefault("citations", []).extend(citation)
            else:
                finding.citations.extend(citation)  # type: ignore[attr-defined]
    except Exception:
        pass
    return finding


def _to_analysis_model(
    a: Dict[str, Any], clause_id: Optional[str], clause_text: str
) -> Any:
    risk_level = str(a.get("risk_level") or "medium")
    payload = {
        "clause_id": clause_id,
        "clause_type": a.get("clause_type") or "unknown",
        "text": clause_text,
        "status": a.get("status") or "OK",
        "score": int(a.get("score") or 0),
        # compat with earlier schemas
        "risk": risk_level,
        "severity_level": risk_level,
        "findings": [_to_finding_model(f) for f in (a.get("findings") or [])],
        "recommendations": [],
        "proposed_text": "",
        "citations": [],
        "diagnostics": [],
    }
    try:
        return AnalysisOutput(**payload)  # type: ignore
    except Exception:
        return payload


def _make_index(text: str, sections: List[Dict[str, Any]]) -> DocIndex:
    clauses: List[Clause] = []
    for i, s in enumerate(sections):
        sp = _norm_span(s.get("span", {}))
        frag = _slice(text or "", sp.start, sp.length)
        cid = f"c{i:03d}"
        try:
            clauses.append(Clause(id=cid, type=s.get("clause_type") or "unknown", text=frag, span=sp, title=s.get("title") or ""))  # type: ignore
        except Exception:
            clauses.append(Clause(id=cid, type=str(s.get("clause_type") or "unknown"), text=frag, span=sp, title=str(s.get("title") or "")))  # type: ignore
    try:
        return DocIndex(document_name=None, language=None, clauses=clauses)  # type: ignore
    except Exception:
        return DocIndex(document_name=None, language=None, clauses=clauses)  # type: ignore


# --- Local helpers for clause mapping ---
def _safe_get(obj, key, *alts, default=None):
    try:
        from collections.abc import (
            Mapping as _Mapping,
        )  # local import to keep scope minimal
    except Exception:
        _Mapping = dict  # fallback
    if isinstance(obj, _Mapping):
        for k in (key, *alts):
            if k in obj and obj[k] is not None:
                return obj[k]
        return default
    for k in (key, *alts):
        val = getattr(obj, k, None)
        if val is not None:
            return val
    return default


def _span_start_len(obj) -> Tuple[int, int]:
    sp = _safe_get(obj, "span", default=None)
    s = int(_safe_get(sp, "start", default=0))
    length = _safe_get(sp, "length", default=None)
    if length is None:
        e = int(_safe_get(sp, "end", default=s))
        length = max(0, e - s)
    else:
        length = int(length or 0)
    return s, length


def _map_clause_id_for_analysis(
    analysis: Dict[str, Any], index: DocIndex
) -> Tuple[Optional[str], str]:
    a_span = _norm_span(_safe_get(analysis, "span", default={}))
    # First: exact start match
    for c in index.clauses or []:
        cs, _ = _span_start_len(c)
        if int(cs) == int(a_span.start):
            clause_id = _safe_get(c, "id", "clause_id", "uuid", default=None)
            clause_text = _safe_get(c, "text", "content", "raw_text", default="")
            return clause_id, clause_text
    # Second: contained within
    for c in index.clauses or []:
        cs, length = _span_start_len(c)
        if int(a_span.start) >= int(cs) and int(a_span.start) < int(cs) + int(length):
            clause_id = _safe_get(c, "id", "clause_id", "uuid", default=None)
            clause_text = _safe_get(c, "text", "content", "raw_text", default="")
            return clause_id, clause_text
    # Third: first same clause_type
    at = str(_safe_get(analysis, "clause_type", default=""))
    for c in index.clauses or []:
        if str(_safe_get(c, "type", "clause_type", default="")) == at:
            clause_id = _safe_get(c, "id", "clause_id", "uuid", default=None)
            clause_text = _safe_get(c, "text", "content", "raw_text", default="")
            return clause_id, clause_text
    # Fallback: first clause
    if index.clauses or []:
        c = index.clauses[0]
        clause_id = _safe_get(c, "id", "clause_id", "uuid", default=None)
        clause_text = _safe_get(c, "text", "content", "raw_text", default="")
        return clause_id, clause_text
    return None, ""


# -----------------------------------------------------------------------------
# Public API (kept intact)
# -----------------------------------------------------------------------------
def analyze_document(
    text: str, document_name: Optional[str] = None, language: Optional[str] = None
) -> DocumentAnalysis:
    """
    NON-BREAKING ENHANCEMENT:
      - Use matcher.classify_sections(text) to produce sections/clauses.
      - Use legal_rules.rules.oilgas_master_agreement.evaluate(text, sections) for analyses & metrics.
      - Build SSOT (DocumentAnalysis) with index, analyses, and summary_* from metrics.
    """
    t = text or ""
    text_for_match, _pd = normalized_view(t)
    type_slug, type_conf, _, score_map = guess_doc_type(t)
    dtype = slug_to_display(type_slug)
    debug_top = [
        {"type": slug_to_display(s), "score": round(v, 3)}
        for s, v in sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]
    sections_norm = _sections_via_matcher(text_for_match)
    raw_analyses, metrics = _rules_evaluate(text_for_match, sections_norm)
    sections: List[Dict[str, Any]] = []
    for s in sections_norm:
        sp = _norm_span(s.get("span", {}))
        rs, re = map_norm_span_to_raw(_pd, sp.start, sp.start + sp.length)
        sections.append({**s, "span": {"start": rs, "length": re - rs}})
    index = _make_index(t, sections)

    analyses_mapped: List[Dict[str, Any]] = []
    for a in raw_analyses:
        aa = dict(a or {})
        sp = _norm_span(aa.get("span", {}))
        rs, re = map_norm_span_to_raw(_pd, sp.start, sp.start + sp.length)
        aa["span"] = {"start": rs, "length": re - rs}
        f_mapped: List[Dict[str, Any]] = []
        for f in aa.get("findings") or []:
            ff = dict(f or {})
            spf = _norm_span(ff.get("span", {}))
            rsf, ref = map_norm_span_to_raw(_pd, spf.start, spf.start + spf.length)
            ff["span"] = {"start": rsf, "length": ref - rsf}
            f_mapped.append(ff)
        aa["findings"] = f_mapped
        analyses_mapped.append(aa)

    # Convert analyses to models/dicts that pipeline_compat can consume
    analyses_models: List[Any] = []
    for a in analyses_mapped:
        clause_id, clause_text = _map_clause_id_for_analysis(a, index)
        analyses_models.append(_to_analysis_model(a, clause_id, clause_text))

    # Summary
    summary_status = str(metrics.get("summary_status", "OK"))
    summary_risk = str(metrics.get("summary_risk", "medium"))
    summary_score = int(metrics.get("summary_score", 0) or 0)

    # Cross refs unused in this enhancement
    cross_refs: List[CrossRef] = []

    try:
        doc = DocumentAnalysis(  # type: ignore
            document_name=document_name,
            summary_score=summary_score,
            summary_risk=summary_risk,  # type: ignore[arg-type]
            summary_status=summary_status,  # type: ignore[arg-type]
            residual_risks=[],
            analyses=analyses_models,
            cross_refs=cross_refs,
            index=index,
            text=t,
        )
    except Exception:
        # Dictionary fallback with same keys
        doc = DocumentAnalysis(  # type: ignore
            document_name=document_name,
            summary_score=summary_score,
            summary_risk=summary_risk,
            summary_status=summary_status,
            residual_risks=[],
            analyses=analyses_models,
            cross_refs=cross_refs,
            index=index,
            text=t,
        )

    extra_summary = {"type": dtype, "type_confidence": type_conf}
    if debug_top:
        extra_summary["debug"] = {"doctype_top": debug_top}
    try:
        object.__setattr__(doc, "summary", extra_summary)
    except Exception:
        try:
            doc.summary = extra_summary  # type: ignore[attr-defined]
        except Exception:
            pass
    return doc


def synthesize_draft(
    analysis_or_text: Union[AnalysisOutput, Dict[str, Any], List[Any], str],
    mode: DraftMode = "friendly",
) -> str:
    """
    Deterministic draft synthesis.
    If a list of analyses is provided, generate a bullet list grouped by clause_type.
    Always returns non-empty text.
    """

    def _short(label: str) -> str:
        return label.replace("_", " ").title()

    # Mode presets (for deterministic phrasing)
    presets = {
        "friendly": {
            "intro": "Suggested edit (friendly):",
            "bullet": "- ",
            "obligation": "should",
        },
        "standard": {
            "intro": "Suggested edit (standard):",
            "bullet": "- ",
            "obligation": "shall",
        },
        "strict": {
            "intro": "Suggested edit (strict):",
            "bullet": "- ",
            "obligation": "shall",
        },
    }
    m = str(mode or "friendly").lower().strip()
    if m not in presets:
        m = "friendly"
    P = presets[m]

    # If list of analyses
    if isinstance(analysis_or_text, list):
        items: List[str] = []
        for a in analysis_or_text[:10]:
            ct = _short(
                str((getattr(a, "clause_type", None) or a.get("clause_type", "clause")))
            )
            findings = (
                getattr(a, "findings", None) or a.get("findings", [])
                if isinstance(a, dict)
                else []
            )
            if findings:
                msg = str(
                    (
                        getattr(findings[0], "message", None)
                        or findings[0].get("message", "")
                        if isinstance(findings[0], dict)
                        else ""
                    )
                )[:160]
                items.append(f"{P['bullet']}{ct}: {msg}")
            else:
                items.append(
                    f"{P['bullet']}{ct}: add {_short('clarity')} and {_short('carve_outs')}."
                )
        head = f"{P['intro']} Document"
        body = [head] + (
            items
            or [
                f"{P['bullet']}General: improve clarity, add notice periods, and {_short('carve_outs')}."
            ]
        )
        return "\n".join(body).strip()

    # Single analysis or text
    clause_type = "clause"
    base_text = ""
    findings: List[Any] = []

    if isinstance(analysis_or_text, str):
        base_text = analysis_or_text
    elif isinstance(analysis_or_text, AnalysisOutput):
        clause_type = analysis_or_text.clause_type or "clause"
        base_text = analysis_or_text.text or ""
        findings = list(analysis_or_text.findings or [])
        if getattr(analysis_or_text, "proposed_text", None):
            base_text = analysis_or_text.proposed_text or base_text
    elif isinstance(analysis_or_text, dict):
        clause_type = str(analysis_or_text.get("clause_type") or "clause")
        base_text = str(
            analysis_or_text.get("proposed_text") or analysis_or_text.get("text") or ""
        )
        findings = list(analysis_or_text.get("findings") or [])
    else:
        base_text = str(analysis_or_text)

    bullets: List[str] = []
    for f in (findings or [])[:5]:
        msg = getattr(f, "message", None) or (
            f.get("message") if isinstance(f, dict) else ""
        )
        code = getattr(f, "code", None) or (
            f.get("code") if isinstance(f, dict) else ""
        )
        if msg:
            bullets.append(f"{P['bullet']}[{code}] {msg}")

    head = f"{P['intro']} {_short(clause_type)}"
    body_parts: List[str] = [head]
    if base_text.strip():
        body_parts.append(f"Current text: {base_text.strip()[:900]}")
    if bullets:
        body_parts.append("Address the following:")
        body_parts.extend(bullets)
    else:
        body_parts.append(
            f"Add {_short('notice period')}, {_short('carve_outs')}, and clear {_short('remedies')}. "
        )

    return "\n".join(body_parts).strip()


def suggest_edits(
    text: str, clause_id: Optional[str] = None, mode: str = "friendly", **kwargs
) -> Dict[str, Any]:
    """
    Deterministic suggestions. Accepts kwargs['clause_type'].
    Builds suggestions with normalized 'range': {'start','length'}.
    """
    doc = analyze_document(text or "")
    clause_type = kwargs.get("clause_type")
    target: Optional[Clause] = None
    a = None

    if clause_id:
        target = next(
            (
                c
                for c in (doc.index.clauses or [])
                if str(_safe_get(c, "id")) == str(clause_id)
            ),
            None,
        )
        if target and not clause_type:
            clause_type = _safe_get(target, "type")
    if clause_type and a is None:
        a = next(
            (
                ai
                for ai in (doc.analyses or [])
                if str(_safe_get(ai, "clause_type")) == str(clause_type)
            ),
            None,
        )
        if target is None:
            target = next(
                (
                    c
                    for c in (doc.index.clauses or [])
                    if str(_safe_get(c, "type")) == str(clause_type)
                ),
                None,
            )

    if target is None and doc.index.clauses:
        target = doc.index.clauses[0]
    if target is None:
        return [
            {
                "suggestion_id": "sg-000",
                "clause_id": None,
                "clause_type": clause_type or "unknown",
                "action": "append",
                "proposed_text": "Add clear obligations and standard carve-outs.",
                "message": "Add clear obligations and standard carve-outs.",
                "reason": "Fallback: no clause segmentation available.",
                "range": {"start": max(0, len(text or "")), "length": 0},
                "span": {
                    "start": max(0, len(text or "")),
                    "end": max(0, len(text or "")),
                },
            }
        ]
    draft_mode = mode if mode in ("friendly", "standard", "strict") else "friendly"
    draft = synthesize_draft(a or _safe_get(target, "text", default=""), draft_mode)

    sp = _safe_get(target, "span", default={})
    start = int(_safe_get(sp, "start", default=0))
    length = int(_safe_get(sp, "length", default=_safe_get(sp, "end", default=0)) or 0)

    tid = _safe_get(target, "id")
    ttype = _safe_get(target, "type")
    card = {
        "suggestion_id": f"sg-{tid}-001",
        "clause_id": tid,
        "clause_type": ttype,
        "action": "replace" if (mode == "strict") else "append",
        "proposed_text": draft,
        "message": draft,
        "reason": "Derived from rule findings.",
        "sources": [],
        "range": {"start": start, "length": max(0, length)},
        "span": {"start": start, "end": start + max(0, length)},
        "hash": tid,
    }
    return [card]
