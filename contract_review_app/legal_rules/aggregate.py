from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from contract_review_app.analysis.agenda import (
    AGENDA_ORDER,
    DEFAULT_SALIENCE,
    SALIENCE_MAX,
    SALIENCE_MIN,
    map_to_agenda_group,
    span_iou,
    stronger,
)

__all__ = ["apply_merge_policy", "apply_legacy_merge_policy"]


def apply_merge_policy(
    findings: Iterable[Dict[str, Any]],
    *,
    use_agenda: bool = True,
) -> List[Dict[str, Any]]:
    """Merge findings using agenda ordering and overlap resolution."""

    items: List[Dict[str, Any]] = [f for f in findings if isinstance(f, dict)]
    if not items:
        return []

    if not use_agenda:
        return apply_legacy_merge_policy(items)

    strict_merge = os.getenv("FEATURE_AGENDA_STRICT_MERGE", "0") == "1"

    groups: List[str] = []
    spans: List[Tuple[int, int] | None] = []
    sort_keys: List[Tuple[int, int, int, str]] = []

    # precompute sort keys, spans, groups; inject resolved salience into finding
    for finding in items:
        group = map_to_agenda_group(finding)
        salience = _resolve_salience(finding, group)

        anchor = finding.get("anchor") or {}
        start_val = _coerce_int(anchor.get("start"))
        end_val = _coerce_int(anchor.get("end"))

        if start_val is not None and end_val is not None and end_val > start_val:
            span = (start_val, end_val)
            start = start_val
        else:
            span = _extract_span(finding)
            start = start_val if start_val is not None else 0

        rid = str(finding.get("rule_id") or "")

        groups.append(group)
        spans.append(span)
        sort_keys.append((AGENDA_ORDER.get(group, 999), -salience, start, rid))

        # persist salience for downstream consumers (non-breaking)
        finding["salience"] = salience

    order = sorted(range(len(items)), key=lambda idx: sort_keys[idx])

    survivors: List[int] = []
    for idx in order:
        span = spans[idx]
        if span is None:
            survivors.append(idx)
            continue

        should_add = True
        ptr = len(survivors) - 1
        while ptr >= 0:
            existing_idx = survivors[ptr]
            existing_span = spans[existing_idx]
            if existing_span is None:
                ptr -= 1
                continue

            # early exit if no more overlaps possible (sorted by start)
            if existing_span[1] <= span[0]:
                break

            # when strict_merge=0 we only collapse overlaps within the same agenda group
            if not strict_merge and groups[idx] != groups[existing_idx]:
                ptr -= 1
                continue

            if span_iou(existing_span, span) >= 0.6:
                champion = stronger(items[idx], items[existing_idx])
                if champion is items[existing_idx]:
                    should_add = False
                    break
                # replace weaker survivor
                survivors.pop(ptr)
            ptr -= 1

        if not should_add:
            continue

        survivors.append(idx)

    return [items[i] for i in survivors]


def _extract_span(finding: Mapping[str, Any]) -> Tuple[int, int] | None:
    """Best-effort span extraction from anchor/start/end/anchors[*]."""
    anchor = finding.get("anchor")
    if isinstance(anchor, Mapping):
        start = _coerce_int(anchor.get("start"))
        end = _coerce_int(anchor.get("end"))
        if start is not None and end is not None and end > start:
            return (start, end)

    start = _coerce_int(finding.get("start"))
    end = _coerce_int(finding.get("end"))
    if start is not None and end is not None and end > start:
        return (start, end)

    anchors = finding.get("anchors")
    if isinstance(anchors, Sequence):
        for candidate in anchors:
            if not isinstance(candidate, Mapping):
                continue
            span = candidate.get("span")
            if isinstance(span, Sequence) and len(span) == 2:
                c_start = _coerce_int(span[0])
                c_end = _coerce_int(span[1])
                if c_start is not None and c_end is not None and c_end > c_start:
                    return (c_start, c_end)
            c_start = _coerce_int(candidate.get("start"))
            c_end = _coerce_int(candidate.get("end"))
            if c_start is not None and c_end is not None and c_end > c_start:
                return (c_start, c_end)
    return None


def _resolve_salience(finding: Mapping[str, Any], group: str) -> int:
    for key in ("salience", "_spec_salience"):
        if key not in finding:
            continue
        value = _coerce_int(finding.get(key))
        if value is None:
            continue
        if value < SALIENCE_MIN:
            return SALIENCE_MIN
        if value > SALIENCE_MAX:
            return SALIENCE_MAX
        return value
    return DEFAULT_SALIENCE.get(group, 50)


# ----------------------- Legacy prioritisation (for rollback) ----------------

_CHANNEL_PRIORITY = {
    "law": 0,
    "policy": 1,
    "substantive": 2,
    "drafting": 3,
    "grammar": 4,
}
_DEFAULT_CHANNEL_RANK = len(_CHANNEL_PRIORITY)

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
            if isinstance(span, (list, tuple)) and len(span) == 2:
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
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if value is None:
        return None
    try:
        return int(str(value))
    except Exception:
        return None
