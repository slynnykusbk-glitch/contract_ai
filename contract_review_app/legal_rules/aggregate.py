"""Utilities for deterministic aggregation of rule findings."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

__all__ = ["apply_merge_policy"]

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


def apply_merge_policy(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a deterministically ordered list with conflicts resolved.

    Conflicts are defined as findings that share the same span (start/end
    coordinates). Only the highest-priority finding for each span is kept.  The
    priority order is: channel, severity, length, rule_id.  The output list is
    always sorted deterministically so identical inputs yield identical outputs.
    """

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
    if isinstance(value, bool):  # bool is subclass of int; filter out explicitly
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if value is None:
        return None
    try:
        return int(str(value))
    except Exception:
        return None
