from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping


_IGNORED_TOP_LEVEL_KEYS = {"cid"}
_IGNORED_META_KEYS = {"pipeline_id", "timings_ms", "debug", "companies_meta"}


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
            ordered.sort(key=lambda c: (
                str(c.get("system", "")),
                str(c.get("instrument", "")),
                str(c.get("section", "")),
                str(c.get("title", "")),
            ))
            item["citations"] = ordered
        conflicts = item.get("conflict_with")
        if isinstance(conflicts, list):
            item["conflict_with"] = sorted(str(c) for c in conflicts)
        ops = item.get("ops")
        if isinstance(ops, list):
            item["ops"] = sorted(ops, key=lambda op: json.dumps(op, sort_keys=True))
        normalized.append(item)
    normalized.sort(
        key=lambda it: (
            str(it.get("rule_id", "")),
            str(it.get("clause_type", "")),
            int(it.get("start", 0) or 0),
            str(it.get("snippet", ""))[:64],
        )
    )
    return normalized


def _sort_rules(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in items or []:
        if isinstance(raw, Mapping):
            out.append(dict(raw))
    out.sort(key=lambda it: (str(it.get("rule_id", "")), str(it.get("status", ""))))
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
    out.sort(key=lambda it: (str(it.get("rule_id", "")), str(it.get("pack", ""))))
    return out


def _clean_summary_block(block: MutableMapping[str, Any]) -> None:
    block.pop("parties", None)
    block.pop("clause_type", None)
    carveouts = block.get("carveouts")
    if isinstance(carveouts, MutableMapping):
        listed = carveouts.get("list")
        if isinstance(listed, list):
            carveouts["list"] = sorted(set(str(item) for item in listed))


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {str(k): _canonicalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    return obj


def normalize_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data = deepcopy(dict(payload or {}))

    for key in _IGNORED_TOP_LEVEL_KEYS:
        data.pop(key, None)

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
        data["clauses"] = _sort_findings(clauses)

    findings_top = data.get("findings")
    if isinstance(findings_top, list):
        data["findings"] = _sort_findings(findings_top)

    meta = data.get("meta")
    if isinstance(meta, MutableMapping):
        for key in _IGNORED_META_KEYS:
            meta.pop(key, None)
        packs = meta.get("active_packs")
        if isinstance(packs, list):
            meta["active_packs"] = sorted(str(p) for p in packs)
        fired = meta.get("fired_rules")
        if isinstance(fired, list):
            meta["fired_rules"] = _sort_fired_rules(fired)

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

    return _canonicalize(data)


def canonical_json(payload: Mapping[str, Any]) -> str:
    canonical = _canonicalize(payload)
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
