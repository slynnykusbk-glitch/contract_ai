from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


_SEVERITY_ORDER = {
    "critical": 4,
    "major": 3,
    "high": 3,
    "medium": 2,
    "minor": 1,
    "low": 1,
    "info": 0,
}

_DROP_PATHS: Sequence[Tuple[str, ...]] = (
    ("cid",),
    ("meta", "api_version"),
    ("meta", "companies_meta"),
    ("meta", "debug"),
    ("meta", "dep"),
    ("meta", "deployment"),
    ("meta", "document_type"),
    ("meta", "endpoint"),
    ("meta", "ep"),
    ("meta", "llm"),
    ("meta", "model"),
    ("meta", "pipeline_id"),
    ("meta", "provider"),
    ("meta", "provider_meta"),
    ("meta", "timings_ms"),
)

_META_ALLOWED_KEYS = {"active_packs", "fired_rules", "rule_count", "rules_coverage"}


def _sort_findings(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in items or []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        law_refs = item.get("law_refs")
        if isinstance(law_refs, list):
            item["law_refs"] = sorted(str(ref) for ref in law_refs)
        citations = item.get("citations")
        if isinstance(citations, list):
            ordered = []
            for citation in citations:
                if isinstance(citation, Mapping):
                    ordered.append(dict(citation))
            ordered.sort(key=_citation_sort_key)
            item["citations"] = ordered
        conflicts = item.get("conflict_with")
        if isinstance(conflicts, list):
            item["conflict_with"] = sorted(str(c) for c in conflicts)
        ops = item.get("ops")
        if isinstance(ops, list):
            item["ops"] = sorted(ops, key=lambda op: json.dumps(op, sort_keys=True))
        normalized.append(item)
    normalized.sort(key=_finding_sort_key)
    return normalized


def _sort_rules(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in items or []:
        if isinstance(raw, Mapping):
            out.append(dict(raw))
    out.sort(key=_coverage_rule_key)
    return out


def _sort_fired_rules(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in items or []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        matched = item.get("matched_triggers")
        if isinstance(matched, Mapping):
            item["matched_triggers"] = {
                str(k): sorted(set(str(vv) for vv in (v or [])))
                for k, v in matched.items()
            }
        positions = item.get("positions") or item.get("trigger_positions")
        if isinstance(positions, list):
            ordered_pos = []
            for pos in positions:
                if isinstance(pos, Mapping):
                    ordered_pos.append({
                        "start": int(pos.get("start", 0) or 0),
                        "end": int(pos.get("end", 0) or 0),
                    })
            ordered_pos.sort(key=lambda p: (p.get("start", 0), p.get("end", 0)))
            item["positions"] = ordered_pos
            item.pop("trigger_positions", None)
        out.append(item)
    out.sort(key=_fired_rule_sort_key)
    return out


def _clean_summary_block(block: MutableMapping[str, Any]) -> None:
    block.pop("parties", None)
    block.pop("clause_type", None)
    carveouts = block.get("carveouts")
    if isinstance(carveouts, MutableMapping):
        listed = carveouts.get("list")
        if isinstance(listed, list):
            carveouts["list"] = sorted(set(str(item) for item in listed))


def _filter_meta(meta: MutableMapping[str, Any]) -> None:
    for key in list(meta.keys()):
        if key not in _META_ALLOWED_KEYS:
            meta.pop(key, None)


def _drop_path(data: MutableMapping[str, Any], path: Sequence[str]) -> None:
    if not path or not isinstance(data, MutableMapping):
        return
    key = path[0]
    if len(path) == 1:
        data.pop(key, None)
        return
    next_value = data.get(key)
    if isinstance(next_value, MutableMapping):
        _drop_path(next_value, path[1:])
        if not next_value:
            data.pop(key, None)
    elif isinstance(next_value, list):
        for item in next_value:
            if isinstance(item, MutableMapping):
                _drop_path(item, path[1:])


def _finding_sort_key(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    if not isinstance(item, Mapping):
        return ("", 0, 0, "", "")
    clause = str(item.get("clause_id") or "")
    start = _coerce_int(item.get("start"))
    span = item.get("span")
    if start == 0 and isinstance(span, Mapping):
        start = _coerce_int(span.get("start"))
    severity = -_SEVERITY_ORDER.get(str(item.get("severity", "")).lower(), 0)
    rule_id = str(item.get("rule_id") or "")
    snippet = str(
        item.get("normalized_snippet")
        or item.get("snippet")
        or item.get("text_hash")
        or ""
    )
    return (clause, start, severity, rule_id, snippet)


def _clause_sort_key(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    if not isinstance(item, Mapping):
        return ("", 0)
    clause_id = str(item.get("id") or item.get("clause_id") or "")
    start = _coerce_int(item.get("start"))
    span = item.get("span")
    if start == 0 and isinstance(span, Mapping):
        start = _coerce_int(span.get("start"))
    return (clause_id, start)


def _sort_clauses(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    for raw in items or []:
        if isinstance(raw, Mapping):
            ordered.append(dict(raw))
    ordered.sort(key=_clause_sort_key)
    return ordered


def _sort_citations(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    for raw in items or []:
        if isinstance(raw, Mapping):
            ordered.append(dict(raw))
    ordered.sort(key=_citation_sort_key)
    return ordered


def _fired_rule_sort_key(item: Mapping[str, Any]) -> Tuple[str, str]:
    if not isinstance(item, Mapping):
        return ("", "")
    name = str(item.get("name") or item.get("rule_id") or "")
    pack = str(item.get("pack") or "")
    return (name, pack)


def _coverage_rule_key(item: Mapping[str, Any]) -> Tuple[str, str]:
    if not isinstance(item, Mapping):
        return ("", "")
    rid = str(item.get("rule_id") or "")
    status = str(item.get("status") or "")
    return (rid, status)


def _citation_sort_key(item: Mapping[str, Any]) -> Tuple[str, str, str, str, str]:
    if not isinstance(item, Mapping):
        return ("", "", "", "", "")
    return (
        str(item.get("system") or ""),
        str(item.get("instrument") or ""),
        str(item.get("section") or ""),
        str(item.get("title") or ""),
        str(item.get("source") or ""),
    )


def _name_key(item: Any) -> str:
    if isinstance(item, Mapping):
        candidate = item.get("name") or item.get("rule_id") or item.get("id") or item.get("pack")
        if candidate is None:
            return ""
        return str(candidate)
    if item is None:
        return ""
    return str(item)


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {str(k): _canonicalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    return obj


def normalize_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data = deepcopy(dict(payload or {}))

    for path in _DROP_PATHS:
        _drop_path(data, path)

    analysis = data.get("analysis")
    if isinstance(analysis, MutableMapping):
        findings = _sort_findings(analysis.get("findings") or [])
        analysis["findings"] = findings

    results = data.get("results")
    if isinstance(results, MutableMapping):
        summary_block = results.get("summary")
        if isinstance(summary_block, MutableMapping):
            _clean_summary_block(summary_block)
        res_analysis = results.get("analysis")
        if isinstance(res_analysis, MutableMapping):
            res_analysis["findings"] = _sort_findings(res_analysis.get("findings") or [])

    clauses = data.get("clauses")
    if isinstance(clauses, list):
        data["clauses"] = _sort_clauses(clauses)

    findings_top = data.get("findings")
    if isinstance(findings_top, list):
        data["findings"] = _sort_findings(findings_top)

    meta = data.get("meta")
    if isinstance(meta, MutableMapping):
        _filter_meta(meta)
        packs = meta.get("active_packs")
        if isinstance(packs, list):
            normalized_packs: List[Any] = []
            for pack in packs:
                if isinstance(pack, Mapping):
                    normalized_packs.append(dict(pack))
                else:
                    normalized_packs.append(pack)
            meta["active_packs"] = sorted(normalized_packs, key=_name_key)
        fired = meta.get("fired_rules")
        if isinstance(fired, list):
            meta["fired_rules"] = _sort_fired_rules(fired)
        coverage_meta = meta.get("rules_coverage")
        if isinstance(coverage_meta, MutableMapping):
            rules_meta = coverage_meta.get("rules")
            if isinstance(rules_meta, list):
                coverage_meta["rules"] = _sort_rules(rules_meta)

    summary = data.get("summary")
    if isinstance(summary, MutableMapping):
        _clean_summary_block(summary)

    coverage = data.get("rules_coverage")
    if isinstance(coverage, MutableMapping):
        rules = coverage.get("rules")
        if isinstance(rules, list):
            coverage["rules"] = _sort_rules(rules)

    document = data.get("document")
    if isinstance(document, MutableMapping):
        summary_doc = document.get("summary")
        if isinstance(summary_doc, MutableMapping):
            _clean_summary_block(summary_doc)
        analyses = document.get("analyses")
        if isinstance(analyses, list):
            document["analyses"] = _sort_findings(analyses)

    recommendations = data.get("recommendations")
    if isinstance(recommendations, list):
        normalized_recs: List[Any] = []
        for rec in recommendations:
            if isinstance(rec, Mapping):
                normalized_recs.append(_canonicalize(rec))
            elif rec is not None:
                normalized_recs.append(str(rec))
        data["recommendations"] = sorted(
            normalized_recs,
            key=lambda rec: json.dumps(rec, sort_keys=True),
        )

    citations = data.get("citations")
    if isinstance(citations, list):
        data["citations"] = _sort_citations(citations)

    return _canonicalize(data)


def canonical_json(payload: Mapping[str, Any]) -> str:
    canonical = _canonicalize(payload)
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
