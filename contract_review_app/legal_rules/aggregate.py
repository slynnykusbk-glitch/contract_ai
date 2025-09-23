"""Utilities for deterministic aggregation of rule findings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Set, Tuple

from contract_review_app.analysis.agenda import (
    agenda_sort_key,
    coerce_int,
    extract_span,
    map_to_agenda_group,
    resolve_salience,
)

__all__ = ["apply_merge_policy", "apply_legacy_merge_policy"]

@dataclass
class _EnrichedFinding:
    finding: MutableMapping[str, Any]
    index: int
    group: str
    salience: int
    span: Tuple[int, int] | None
    sort_key: Tuple[int, int, int, str]
    entity_keys: Set[str]


def apply_merge_policy(
    findings: Iterable[Dict[str, Any]],
    *,
    strict_merge: bool = False,
) -> List[Dict[str, Any]]:
    """Apply agenda-based ordering and overlap resolution to ``findings``."""

    items: List[MutableMapping[str, Any]] = [
        f for f in findings if isinstance(f, MutableMapping)
    ]
    if not items:
        return []

    enriched: List[_EnrichedFinding] = []
    for idx, finding in enumerate(items):
        group = map_to_agenda_group(finding)
        salience = resolve_salience(finding, group=group)
        finding["salience"] = salience
        span = extract_span(finding)
        start = span[0] if span is not None else None
        sort_key = agenda_sort_key(finding, group=group, salience=salience, start=start)
        entity_keys = _entity_key_set(finding)
        enriched.append(
            _EnrichedFinding(
                finding=finding,
                index=idx,
                group=group,
                salience=salience,
                span=span,
                sort_key=sort_key,
                entity_keys=entity_keys,
            )
        )

    survivors = _select_survivors(enriched, strict_merge=strict_merge)
    survivors.sort(key=lambda item: (item.sort_key, item.index))
    return [entry.finding for entry in survivors]


def _select_survivors(
    candidates: Sequence[_EnrichedFinding],
    *,
    strict_merge: bool,
) -> List[_EnrichedFinding]:
    ordered = sorted(candidates, key=lambda entry: (entry.sort_key, entry.index))
    survivors: List[_EnrichedFinding] = []
    for candidate in ordered:
        span = candidate.span
        if span is None:
            survivors.append(candidate)
            continue

        keep = True
        for existing in survivors:
            other_span = existing.span
            if other_span is None:
                continue
            if not _spans_overlap(span, other_span):
                continue
            if not _should_eliminate(existing, candidate, strict_merge=strict_merge):
                continue
            keep = False
            break
        if keep:
            survivors.append(candidate)
    return survivors


def _spans_overlap(lhs: Tuple[int, int], rhs: Tuple[int, int]) -> bool:
    start_a, end_a = lhs
    start_b, end_b = rhs
    if end_a is None or end_b is None:
        return False
    if start_a is None or start_b is None:
        return False
    if end_a == start_a and end_b == start_b:
        return start_a == start_b
    if end_a <= start_a or end_b <= start_b:
        return False

    intersection = min(end_a, end_b) - max(start_a, start_b)
    if intersection <= 0:
        return False

    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0:
        return False

    iou = intersection / union
    if iou >= 0.6:
        return True

    span_a = end_a - start_a
    span_b = end_b - start_b
    smaller = min(span_a, span_b)
    return intersection >= smaller


def _should_eliminate(
    existing: _EnrichedFinding,
    candidate: _EnrichedFinding,
    *,
    strict_merge: bool,
) -> bool:
    if strict_merge:
        return True
    if existing.group != candidate.group:
        return False
    if not existing.entity_keys or not candidate.entity_keys:
        return False
    return bool(existing.entity_keys & candidate.entity_keys)


def _entity_key_set(finding: Mapping[str, Any]) -> Set[str]:
    tokens: Set[str] = set()

    def _add(value: Any) -> None:
        token = _normalize_entity_token(value)
        if token:
            tokens.add(token)

    _add(finding.get("rule_id"))
    for key in (
        "entity",
        "entity_key",
        "legal_entity",
        "topic",
        "issue_id",
        "canonical_name",
    ):
        _add(finding.get(key))

    meta = finding.get("meta")
    if isinstance(meta, Mapping):
        for key in (
            "entity_id",
            "entity",
            "entity_key",
            "legal_entity",
            "legal_issue",
            "topic",
            "subtopic",
            "issue_id",
        ):
            _add(meta.get(key))

    return tokens


def _normalize_entity_token(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        token = value.strip().lower()
        return token or None
    try:
        token = str(value).strip().lower()
    except Exception:
        return None
    return token or None


# Legacy prioritisation ----------------------------------------------------

# Priority order for channels when conflicts share the same span.
_CHANNEL_PRIORITY = {
    "law": 0,
    "policy": 1,
    "substantive": 2,
    "drafting": 3,
    "grammar": 4,
}
_DEFAULT_CHANNEL_RANK = len(_CHANNEL_PRIORITY)

# Severity ranking (higher numbers mean higher severity).
_SEVERITY_PRIORITY = {
    "critical": 4,
    "severe": 4,
    "blocker": 4,
    "major": 3,
    "high": 3,
    "medium": 2,
    "moderate": 2,
    "minor": 1,
    "low": 1,
    "info": 0,
    "informational": 0,
}

_MAX_POSITION = 10 ** 12


def apply_legacy_merge_policy(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Legacy merge behaviour kept for feature flag rollbacks."""

    items = [f for f in findings if isinstance(f, dict)]
    if not items:
        return []

    buckets: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for idx, finding in enumerate(items):
        key = _bucket_key(finding, idx)
        buckets.setdefault(key, []).append(finding)

    resolved: List[Dict[str, Any]] = []
    for key, bucket in buckets.items():
        if key[0] == "span":
            best = min(bucket, key=_priority_tuple)
            resolved.append(best)
        else:
            resolved.extend(sorted(bucket, key=_priority_tuple))

    resolved.sort(key=_final_sort_key)
    return list(resolved)


def _bucket_key(finding: Dict[str, Any], idx: int) -> Tuple[Any, ...]:
    start = _coerce_int(finding.get("start"))
    end = _coerce_int(finding.get("end"))
    if start is not None and end is not None:
        return ("span", start, end)

    anchors = finding.get("anchors")
    if isinstance(anchors, list) and anchors:
        anchor = anchors[0]
        if isinstance(anchor, dict):
            span = anchor.get("span")
            if (
                isinstance(span, (list, tuple))
                and len(span) == 2
            ):
                a_start = _coerce_int(span[0])
                a_end = _coerce_int(span[1])
                if a_start is not None and a_end is not None:
                    return ("span", a_start, a_end)
    return ("idx", idx)


def _priority_tuple(finding: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        _channel_rank(finding),
        -_severity_rank(finding),
        -_span_length(finding),
        str(finding.get("rule_id") or ""),
    )


def _final_sort_key(finding: Dict[str, Any]) -> Tuple[Any, ...]:
    start = _coerce_int(finding.get("start"))
    end = _coerce_int(finding.get("end"))
    if start is None:
        start = _MAX_POSITION
    if end is None:
        end = _MAX_POSITION
    return (
        start,
        end,
        _channel_rank(finding),
        -_severity_rank(finding),
        -_span_length(finding),
        str(finding.get("rule_id") or ""),
    )


def _channel_rank(finding: Dict[str, Any]) -> int:
    channel = _infer_channel(finding)
    return _CHANNEL_PRIORITY.get(channel.lower(), _DEFAULT_CHANNEL_RANK)


def _infer_channel(finding: Dict[str, Any]) -> str:
    channel = finding.get("channel")
    if isinstance(channel, str) and channel.strip():
        return channel.strip()

    source = finding.get("source")
    if isinstance(source, str) and source.strip():
        if source.strip().lower() == "constraints":
            return "Law"

    rule_id = finding.get("rule_id")
    if isinstance(rule_id, str) and rule_id.upper().startswith("L2"):
        return "Law"

    return ""


def _severity_rank(finding: Dict[str, Any]) -> int:
    severity = finding.get("severity") or finding.get("severity_level")
    if not isinstance(severity, str):
        severity = str(severity or "")
    severity_norm = severity.strip().lower()
    return _SEVERITY_PRIORITY.get(severity_norm, 0)


def _span_length(finding: Dict[str, Any]) -> int:
    start = _coerce_int(finding.get("start"))
    end = _coerce_int(finding.get("end"))
    if start is not None and end is not None:
        length = end - start
        if length >= 0:
            return length
    snippet = finding.get("snippet") or finding.get("message") or ""
    return len(str(snippet))


def _coerce_int(value: Any) -> int | None:
    return coerce_int(value)
