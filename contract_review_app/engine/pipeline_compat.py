from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .doc_type import guess_doc_type, slug_to_display

# Public API:
#   to_panel_shape(ssot) -> (analysis:dict, results:dict, clauses:list[dict])


# --------------------- helpers ---------------------
def _is_dict(o: Any) -> bool:
    return isinstance(o, dict)


def _dump(obj: Any) -> Dict[str, Any]:
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[attr-defined]
        if hasattr(obj, "dict"):
            return obj.dict()  # type: ignore[attr-defined]
        if _is_dict(obj):
            return obj
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
    except Exception:
        return {}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if _is_dict(obj):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_list(obj: Any, key: str) -> List[Any]:
    v = _get(obj, key, [])
    if v is None:
        return []
    return list(v) if isinstance(v, list) else [v]


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _risk_to_ord(r: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get((r or "medium").lower(), 1)


def _ord_to_risk(i: int) -> str:
    table = ["low", "medium", "high", "critical"]
    if i < 0:
        return table[0]
    if i >= len(table):
        return table[-1]
    return table[i]


def _headline(analyses: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not analyses:
        return None
    # risk desc, findings count desc, score asc, clause_type/name asc — deterministic
    def key(a: Dict[str, Any]) -> tuple:
        risk = _risk_to_ord(str(a.get("risk_level") or a.get("risk") or a.get("severity") or "medium"))
        fcnt = len(a.get("findings") or [])
        score = _to_int(a.get("score") or 0, 0)
        name = str(a.get("clause_type") or a.get("type") or "")
        return (risk, fcnt, -score, name)

    return max(analyses, key=key)


def _build_analysis(head: Dict[str, Any] | None, doc: Dict[str, Any]) -> Dict[str, Any]:
    if not head:
        return {
            "status": str(_get(doc, "summary_status", "OK") or "OK"),
            "risk_level": str(_get(doc, "summary_risk", "medium") or "medium"),
            "score": _to_int(_get(doc, "summary_score", 0), 0),
            "findings": [],
        }
    risk = str(head.get("risk") or head.get("risk_level") or head.get("severity") or "medium")
    return {
        "status": str(head.get("status", "OK") or "OK"),
        "risk_level": risk,
        "score": _to_int(head.get("score") or 0, 0),
        "findings": list((head.get("findings") or []))[:5],
    }


def _build_results(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for a in analyses:
        ctype = str(a.get("clause_type") or a.get("type") or "clause")
        buckets.setdefault(ctype, []).append(a)

    out: Dict[str, Any] = {}
    for ctype in sorted(buckets.keys(), key=lambda s: s.lower()):
        items = buckets[ctype]
        worst_risk = max((_risk_to_ord(str(i.get("risk_level") or i.get("risk") or i.get("severity") or "medium")) for i in items), default=1)
        scores = [_to_int(i.get("score") or 0, 0) for i in items]
        avg_score = _to_int(round(sum(scores) / len(scores))) if scores else 0
        findings: List[Any] = []
        for i in items:
            findings.extend(list(i.get("findings") or []))
        out[ctype] = {
            "status": str(items[0].get("status", "OK") or "OK"),
            "risk_level": _ord_to_risk(worst_risk),
            "score": avg_score,
            "findings": findings[:10],
        }
    return out


def _build_clauses(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    idx = _get(doc, "index", {}) or {}
    raw = _get_list(idx, "clauses")
    # sort deterministically by start asc, then title
    def key(c: Any) -> tuple:
        c = _dump(c)
        sp = c.get("span") or {}
        start = _to_int((sp.get("start") if isinstance(sp, dict) else _get(sp, "start", 0)) if sp else c.get("start", 0), 0)
        title = str(c.get("title") or "")
        return (start, title)

    result: List[Dict[str, Any]] = []
    for c in sorted(( _dump(x) for x in raw ), key=key):
        sp = c.get("span") or {}
        if isinstance(sp, dict):
            start = _to_int(sp.get("start", 0), 0)
            length = _to_int(sp.get("length", sp.get("end", 0) - sp.get("start", 0)), 0)
        else:
            start = _to_int(_get(sp, "start", 0), 0)
            length = _to_int(_get(sp, "length", _get(sp, "end", 0) - _get(sp, "start", 0)), 0)
        start = max(0, start)
        length = max(0, length)
        result.append(
            {
                "id": str(c.get("id") or ""),
                "type": str(c.get("type") or c.get("clause_type") or "clause"),
                "title": str(c.get("title") or ""),
                "span": {"start": start, "length": length},
            }
        )
    return result


# --------------------- public API ---------------------
def to_panel_shape(ssot: dict | Any) -> Tuple[dict, dict, list[dict]]:
    """
    Pure adapter from engine SSOT to panel-friendly shapes.
    Returns: (analysis, results, clauses)
    """
    doc = _dump(ssot or {})
    analyses_raw = _get_list(doc, "analyses")
    analyses = [_dump(a) for a in analyses_raw]

    head = _headline(analyses)
    analysis = _build_analysis(head, doc)

    doc_summary = _get(doc, "summary", {}) or {}
    if "type" not in doc_summary:
        slug, conf, _, score_map = guess_doc_type(str(_get(doc, "text", "")))
        dtype = slug_to_display(slug)
        debug_top = [
            {"type": slug_to_display(s), "score": round(v, 3)}
            for s, v in sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]
        doc_summary = {"type": dtype, "type_confidence": conf}
        if debug_top:
            doc_summary["debug"] = {"doctype_top": debug_top}

    results = _build_results(analyses)
    if doc_summary:
        results.setdefault("summary", {})
        results["summary"]["type"] = doc_summary.get("type")
        results["summary"]["type_confidence"] = doc_summary.get("type_confidence")
        if doc_summary.get("debug"):
            results["summary"]["debug"] = doc_summary["debug"]
        doc["summary"] = {**doc_summary}

    clauses = _build_clauses(doc)
    return analysis, results, clauses
