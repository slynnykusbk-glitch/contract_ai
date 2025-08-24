from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from itertools import islice

# Prefer YAML/runtime rule registry when available
try:
    from contract_review_app.legal_rules import registry as _reg  # type: ignore
except Exception:
    _reg = None  # type: ignore

# Optional lightweight loader for simple YAML packs
try:
    from contract_review_app.legal_rules import loader as _loader  # type: ignore
except Exception:
    _loader = None  # type: ignore

# --- Safe engine import with fallback ---
try:
    from contract_review_app.engine import pipeline as _engine  # type: ignore
except Exception:
    class _DummyEngine:  # minimal SSOT-compatible fallback
        @staticmethod
        def analyze_document(text: str) -> Dict[str, Any]:
            return {
                "summary_status": "OK",
                "summary_risk": "medium",
                "summary_score": 0,
                "analyses": [],
                "index": {"clauses": []},
                "text": str(text or ""),
            }

        @staticmethod
        def run_pipeline(text: str) -> Dict[str, Any]:
            return _DummyEngine.analyze_document(text)

    _engine = _DummyEngine()  # type: ignore

try:
    from contract_review_app.engine import pipeline_compat as _compat  # type: ignore
    _to_panel_shape = getattr(_compat, "to_panel_shape", None)
except Exception:
    _to_panel_shape = None

if TYPE_CHECKING:
    try:
        from contract_review_app.core.schemas import AnalyzeIn, DraftIn, SuggestIn, QARecheckIn  # type: ignore
    except Exception:  # pragma: no cover
        AnalyzeIn = DraftIn = SuggestIn = QARecheckIn = Any  # type: ignore


# ----------------- Utilities -----------------
def _safe_dump(obj: Any) -> Dict[str, Any]:
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[attr-defined]
        if hasattr(obj, "dict"):
            return obj.dict()  # type: ignore[attr-defined]
        if isinstance(obj, dict):
            return obj
        # shallow attribute dump
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
    except Exception:
        return {}


def _risk_to_ord(s: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get((s or "").lower(), 1)


def _ord_to_risk(i: int) -> str:
    table = ["low", "medium", "high", "critical"]
    if i < 0:
        i = 0
    if i >= len(table):
        i = len(table) - 1
    return table[i]


def _pick_headline(analyses: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Choose the "headline" analysis deterministically.
    Accepts either dicts or objects with attributes (e.g., pydantic models).
    """
    items = [_safe_dump(a) for a in (analyses or [])]
    if not items:
        return None
    return max(
        items,
        key=lambda a: (
            _risk_to_ord(str(a.get("risk_level") or a.get("risk") or a.get("severity") or "medium")),
            len(a.get("findings") or []),
            -int(a.get("score") or 0),
            str(a.get("clause_type") or a.get("type") or ""),
        ),
    )


def _aggregate_results(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for a in analyses:
        ctype = str(a.get("clause_type") or a.get("type") or "clause")
        buckets.setdefault(ctype, []).append(a)

    out: Dict[str, Any] = {}
    for ctype in sorted(buckets.keys(), key=lambda s: s.lower()):
        items = buckets[ctype]
        worst_risk = max((_risk_to_ord(str(i.get("risk_level") or i.get("risk") or i.get("severity") or "medium")) for i in items), default=1)
        scores = [int(i.get("score") or 0) for i in items if isinstance(i.get("score"), (int, float, str))]
        avg_score = int(round(sum(scores) / len(scores))) if scores else 0
        findings: List[Any] = []
        for i in items:
            findings.extend(list(i.get("findings") or []))
        findings = findings[:10]
        out[ctype] = {
            "status": (items[0].get("status") or "OK"),
            "risk_level": _ord_to_risk(worst_risk),
            "score": int(avg_score),
            "findings": findings,
        }
    return out


def _fallback_panel(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    analyses = list(doc.get("analyses") or [])
    headline = _pick_headline(analyses) or {}
    analysis = {
        "status": headline.get("status") or doc.get("summary_status") or "OK",
        "risk_level": headline.get("risk_level") or headline.get("risk") or doc.get("summary_risk") or "medium",
        "score": int(headline.get("score") or doc.get("summary_score") or 0),
        "findings": list(islice((headline.get("findings") or []), 5)),
    }
    results = _aggregate_results(analyses)

    idx = (doc.get("index") or {})
    clauses_raw = list(idx.get("clauses") or [])
    # deterministic ordering: by start asc, then title
    def _key(c: Dict[str, Any]) -> Tuple[int, str]:
        sp = c.get("span") or {}
        return (int(sp.get("start") or 0), str(c.get("title") or ""))

    clauses: List[Dict[str, Any]] = []
    for c in sorted(clauses_raw, key=_key):
        sp = (c.get("span") or {})
        clauses.append(
            {
                "id": c.get("id"),
                "type": c.get("type") or c.get("clause_type") or "clause",
                "title": c.get("title") or "",
                "span": {"start": int(sp.get("start") or 0), "length": int(sp.get("length") or 0)},
            }
        )
    return analysis, results, clauses


def _ensure_analysis_keys(a: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(a or {})
    if "risk_level" not in a:
        a["risk_level"] = a.get("risk") or a.get("severity") or "medium"
    a["score"] = int(a.get("score") or 0)
    return a


def _ensure_results_keys(results: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in sorted((results or {}).keys(), key=lambda s: s.lower()):
        v = dict(results[k] or {})
        if "risk_level" not in v:
            v["risk_level"] = v.get("risk") or v.get("severity") or "medium"
        v["score"] = int(v.get("score") or 0)
        out[k] = v
    return out


def _coerce_patch_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(by_alias=True)  # type: ignore[attr-defined]
        if hasattr(obj, "dict"):
            return obj.dict(by_alias=True)  # type: ignore[attr-defined]
    except Exception:
        pass
    out: Dict[str, Any] = {}
    for k in ("range", "span", "replacement", "text"):
        if hasattr(obj, k):
            out[k] = getattr(obj, k)
    return out


def _apply_patches(text: str, changes: Optional[List[Any]]) -> str:
    if not changes:
        return text or ""
    base = text or ""
    n = len(base)
    items: List[Tuple[int, int, str]] = []
    for raw in changes:
        ch = _coerce_patch_dict(raw) or {}
        src = ch.get("range")
        if not isinstance(src, dict):
            src = ch.get("span") or {}
        start = src.get("start", 0)
        length = src.get("length", None)
        end = src.get("end", None)
        try:
            start = int(start)
        except Exception:
            start = 0
        if length is None and end is not None:
            try:
                end = int(end)
            except Exception:
                end = start
            length = max(0, end - start)
        elif length is None:
            length = 0
        else:
            try:
                length = int(length)
            except Exception:
                length = 0
        if start < 0:
            start = 0
        if length < 0:
            length = 0
        end_pos = start + length
        if end_pos < start:
            end_pos = start
        if start > n:
            start = n
        if end_pos > n:
            end_pos = n
        rep = ch.get("replacement", None)
        if rep is None:
            rep = ch.get("text", "")
        rep = "" if rep is None else str(rep)
        items.append((start, end_pos, rep))
    # sort by start asc, ignore overlaps deterministically
    items.sort(key=lambda t: (t[0], t[1]))
    out: List[str] = []
    cur = 0
    for s, e, rep in items:
        if s < cur or s > n or e > n:
            continue  # ignore overlaps/OOB
        out.append(base[cur:s])
        out.append(rep)
        cur = e
    out.append(base[cur:])
    return "".join(out)


def _norm_range(rng: Any) -> Dict[str, int]:
    if not isinstance(rng, dict):
        return {"start": 0, "length": 0}
    start = rng.get("start", 0)
    length = rng.get("length", None)
    end = rng.get("end", None)
    try:
        start = int(start)
    except Exception:
        start = 0
    if length is None and end is not None:
        try:
            end = int(end)
        except Exception:
            end = start
        length = max(0, end - start)
    elif length is None:
        length = 0
    else:
        try:
            length = int(length)
        except Exception:
            length = 0
    if start < 0:
        start = 0
    if length < 0:
        length = 0
    return {"start": start, "length": length}


def _norm_suggestion(s: Any) -> Dict[str, Any]:
    d = _safe_dump(s)
    msg = d.get("message")
    if not msg:
        msg = d.get("text") or d.get("proposed_text") or d.get("proposed") or d.get("reason") or ""
    action = d.get("action") or "replace"
    rng = d.get("range")
    if not isinstance(rng, dict):
        rng = d.get("span") or {}
    d["message"] = str(msg)
    d["action"] = str(action)
    d["range"] = _norm_range(rng)
    return d


# ----------------- Public API -----------------
async def run_analyze(inp: "AnalyzeIn") -> Dict[str, Any]:
    text = getattr(inp, "text", "") or ""
    # Prefer YAML runtime for now (registry-based)
    if _reg is not None and hasattr(_reg, "run_all"):
        try:
            doc_obj = _reg.run_all(text)  # type: ignore[attr-defined]
        except Exception:
            doc_obj = None
    else:
        doc_obj = None

    if doc_obj is None:
        if hasattr(_engine, "analyze_document"):
            doc_obj = _engine.analyze_document(text)
        elif hasattr(_engine, "run_pipeline"):
            doc_obj = _engine.run_pipeline(text=text)  # type: ignore
        else:
            # fallback engine instance might be a class with staticmethod
            doc_obj = _engine.analyze_document(text)  # type: ignore

    doc = _safe_dump(doc_obj)

    if _to_panel_shape:
        try:
            analysis, results, clauses = _to_panel_shape(doc_obj)  # type: ignore
        except Exception:
            analysis, results, clauses = _fallback_panel(doc)
    else:
        analysis, results, clauses = _fallback_panel(doc)

    analysis = _ensure_analysis_keys(analysis)
    results = _ensure_results_keys(results)
    if _loader is not None:
        analysis["findings"] = _loader.match_text(text)
    return {"analysis": analysis, "results": results, "clauses": clauses, "document": doc}


async def run_gpt_draft(inp: "DraftIn") -> Dict[str, Any]:
    text = getattr(inp, "text", "") or ""
    clause_type = getattr(inp, "clause_type", None)
    mode = getattr(inp, "mode", None)

    req = {"text": text, "clause_type": clause_type, "mode": mode}
    res = None
    try:
        if hasattr(_engine, "gpt_draft"):
            res = _engine.gpt_draft(**{k: v for k, v in req.items() if v is not None})  # type: ignore
        elif hasattr(_engine, "run_gpt_draft"):
            res = _engine.run_gpt_draft(**{k: v for k, v in req.items() if v is not None})  # type: ignore
        elif hasattr(_engine, "run_gpt_drafting_pipeline"):
            res = _engine.run_gpt_drafting_pipeline(**{k: v for k, v in req.items() if v is not None})  # type: ignore
    except Exception:
        res = None

    out = _safe_dump(res)
    draft_text = str(out.get("draft_text") or "").strip()
    if not draft_text:
        snippet = " ".join((text or "").split())
        if len(snippet) > 300:
            snippet = snippet[:300] + "…"
        draft_text = f"Proposed {clause_type or 'clause'} revision:\n{snippet or '—'}"
        out = {
            "draft_text": draft_text,
            "alternatives": out.get("alternatives") or [{"draft_text": draft_text}],
            "meta": {"model": "rule-based", "clause_type": clause_type or "unknown", "title": clause_type or "Clause"},
            "model": "rule-based",
        }
    else:
        if "model" not in out:
            out["model"] = "gpt"
        if "alternatives" not in out or not isinstance(out["alternatives"], list):
            out["alternatives"] = []
        out.setdefault("meta", {})  # optional container
        out["meta"].setdefault("model", out.get("model"))
        out["meta"].setdefault("clause_type", clause_type or "unknown")
        out["meta"].setdefault("title", clause_type or "Clause")
    return _safe_dump(out)


async def run_suggest_edits(inp: "SuggestIn") -> Dict[str, Any]:
    text = getattr(inp, "text", "") or ""
    clause_id = getattr(inp, "clause_id", None)
    clause_type = getattr(inp, "clause_type", None)
    mode = getattr(inp, "mode", None)
    req = {"text": text, "clause_id": clause_id, "clause_type": clause_type, "mode": mode}

    payload = None
    try:
        if hasattr(_engine, "suggest_edits"):
            payload = _engine.suggest_edits(**{k: v for k, v in req.items() if v is not None})  # type: ignore
        elif hasattr(_engine, "pipeline") and hasattr(_engine.pipeline, "suggest_edits"):  # type: ignore[attr-defined]
            payload = _engine.pipeline.suggest_edits(**{k: v for k, v in req.items() if v is not None})  # type: ignore[attr-defined]
    except Exception:
        payload = None

    suggestions: List[Dict[str, Any]] = []
    if payload is not None:
        dump = _safe_dump(payload)
        src_list = dump.get("suggestions")
        if not isinstance(src_list, list):
            src_list = dump.get("edits") or dump.get("items") or []
        for s in (src_list or []):
            suggestions.append(_norm_suggestion(s))

    if not suggestions:
        # deterministic fallback: append a newline for readability
        msg = "Append a newline for readability"
        suggestions.append(
            {
                "message": msg,
                "action": "append",
                "range": {"start": max(0, len(text or "")), "length": 0},
                "clause_id": clause_id,
                "clause_type": clause_type,
                "reason": "Formatting improvement (fallback)",
            }
        )
    return {"suggestions": suggestions}


async def run_qa_recheck(inp: "QARecheckIn") -> Dict[str, Any]:
    original_text = getattr(inp, "text", "") or ""
    # BEFORE
    if hasattr(_engine, "analyze_document"):
        before_obj = _engine.analyze_document(original_text)
    elif hasattr(_engine, "run_pipeline"):
        before_obj = _engine.run_pipeline(text=original_text)  # type: ignore
    else:
        before_obj = _engine.analyze_document(original_text)  # type: ignore
    before = _safe_dump(before_obj)

    # Apply patches
    changes = getattr(inp, "applied_changes", None) or []
    patched_text = _apply_patches(original_text, list(changes))

    # AFTER
    if hasattr(_engine, "analyze_document"):
        after_obj = _engine.analyze_document(patched_text)
    elif hasattr(_engine, "run_pipeline"):
        after_obj = _engine.run_pipeline(text=patched_text)  # type: ignore
    else:
        after_obj = _engine.analyze_document(patched_text)  # type: ignore
    after = _safe_dump(after_obj)

    # Deltas (flat)
    rb = str(before.get("summary_risk", "medium"))
    ra = str(after.get("summary_risk", "medium"))
    sb = int(before.get("summary_score", 0) or 0)
    sa = int(after.get("summary_score", 0) or 0)

    risk_delta = max(-3, min(3, _risk_to_ord(ra) - _risk_to_ord(rb)))
    score_delta = max(-100, min(100, sa - sb))

    # residual risks: pick top by severity from AFTER
    analyses_after = [_safe_dump(a) for a in list(after.get("analyses") or [])]
    headline = _pick_headline(analyses_after) or {}
    findings = [_safe_dump(f) for f in list(headline.get("findings") or [])]

    def _sev_ord(f: Dict[str, Any]) -> int:
        return _risk_to_ord(str(f.get("severity") or f.get("risk") or f.get("severity_level") or "medium"))

    findings_sorted = sorted(
        findings,
        key=lambda f: (_sev_ord(f), str(f.get("code") or ""), str(f.get("message") or "")),
        reverse=True,
    )

    residuals: List[Dict[str, Any]] = []
    for f in findings_sorted[:3]:
        residuals.append(
            {
                "code": f.get("code"),
                "message": f.get("message"),
                "severity": f.get("severity") or f.get("risk") or f.get("severity_level"),
            }
        )

    return {
        "status": "ok",
        "risk_delta": risk_delta,
        "score_delta": score_delta,
        "status_from": before.get("summary_status", "OK"),
        "status_to": after.get("summary_status", "OK"),
        "residual_risks": residuals,
    }
