"""Deterministic normalisation helpers for contract API responses."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Tuple

_SEVERITY_ORDER = {
    "critical": 4,
    "major": 3,
    "high": 3,
    "medium": 2,
    "minor": 1,
    "low": 1,
    "info": 0,
}

_DROP_PATHS: set[Tuple[str, ...]] = {
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
}

_META_ALLOWED_KEYS = {"active_packs", "fired_rules", "rule_count", "rules_coverage"}

_PARTY_KEYS = {"role", "name"}


def normalize_for_diff(payload: Any) -> Any:
    """Return a deep-copied payload with stable key ordering and list sorting."""

    return _normalize(deepcopy(payload))


def _normalize(node: Any, path: Tuple[str, ...] = ()) -> Any:
    if isinstance(node, dict):
        return _normalize_dict(node, path)
    if isinstance(node, list):
        return _normalize_list(node, path)
    return node


def _normalize_dict(data: dict[str, Any], path: Tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(data.keys()):
        next_path = path + (key,)
        if next_path in _DROP_PATHS:
            continue
        if path == ("meta",) and key not in _META_ALLOWED_KEYS:
            continue
        value = _normalize(data[key], next_path)
        if key == "parties" and path and path[-1] == "summary":
            value = _sanitize_parties(value)
        result[key] = value
    return result


def _sanitize_parties(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    trimmed: list[dict[str, Any]] = []
    changed = False
    for party in value:
        if not isinstance(party, dict):
            continue
        minimal = {
            k: party[k] for k in _PARTY_KEYS if k in party and party[k] is not None
        }
        if set(party.keys()) - _PARTY_KEYS:
            changed = True
        if minimal:
            trimmed.append(minimal)
    if changed:
        return trimmed
    return value


def _normalize_list(items: Iterable[Any], path: Tuple[str, ...]) -> list[Any]:
    normalized = [_normalize(item, path) for item in items]
    if not path:
        return normalized
    key = path[-1]
    if key == "findings":
        normalized.sort(key=_finding_sort_key)
    elif key == "clauses":
        normalized.sort(key=_clause_sort_key)
    elif path == ("meta", "active_packs"):
        normalized = sorted(normalized)
    elif path == ("meta", "fired_rules"):
        normalized.sort(key=_fired_rule_key)
    elif len(path) >= 2 and path[-2:] == ("rules_coverage", "rules"):
        normalized.sort(key=_coverage_rule_key)
    elif key == "citations":
        normalized.sort(key=_citation_sort_key)
    return normalized


def _finding_sort_key(item: Any) -> Tuple[Any, ...]:
    if not isinstance(item, dict):
        return ("", 0, 0, "", "")
    clause = str(item.get("clause_id") or "")
    start = _coerce_int(item.get("start"))
    if start == 0 and isinstance(item.get("span"), dict):
        start = _coerce_int(item["span"].get("start"))
    severity = -_SEVERITY_ORDER.get(str(item.get("severity", "")).lower(), 0)
    rule_id = str(item.get("rule_id") or "")
    snippet_key = str(
        item.get("normalized_snippet")
        or item.get("snippet")
        or item.get("text_hash")
        or ""
    )
    return (clause, start, severity, rule_id, snippet_key)


def _clause_sort_key(item: Any) -> Tuple[Any, ...]:
    if not isinstance(item, dict):
        return ("", 0)
    clause_id = str(item.get("id") or item.get("clause_id") or "")
    start = _coerce_int(item.get("start"))
    if start == 0 and isinstance(item.get("span"), dict):
        start = _coerce_int(item["span"].get("start"))
    return (clause_id, start)


def _fired_rule_key(item: Any) -> Tuple[str, str]:
    if not isinstance(item, dict):
        return ("", "")
    name = str(item.get("name") or "")
    rule_id = str(item.get("rule_id") or "")
    pack = str(item.get("pack") or "")
    return (name or rule_id, pack)


def _coverage_rule_key(item: Any) -> Tuple[str, str]:
    if not isinstance(item, dict):
        return ("", "")
    rid = str(item.get("rule_id") or "")
    status = str(item.get("status") or "")
    return (rid, status)


def _citation_sort_key(item: Any) -> Tuple[str, str, str, str, str]:
    if not isinstance(item, dict):
        return ("", "", "", "", "")
    return (
        str(item.get("system") or ""),
        str(item.get("instrument") or ""),
        str(item.get("section") or ""),
        str(item.get("title") or ""),
        str(item.get("source") or ""),
    )


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0
