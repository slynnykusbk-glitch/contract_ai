"""Agenda helpers for deterministic merge ordering."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

__all__ = [
    "AGENDA_ORDER",
    "DEFAULT_SALIENCE",
    "MAX_POSITION",
    "agenda_sort_key",
    "coerce_int",
    "extract_span",
    "infer_channel",
    "map_to_agenda_group",
    "resolve_salience",
]

AGENDA_ORDER: Dict[str, int] = {
    "presence": 10,
    "substantive": 20,
    "policy": 30,
    "law": 30,
    "drafting": 40,
    "grammar": 50,
    "fixup": 60,
}

DEFAULT_SALIENCE: Dict[str, int] = {
    "presence": 95,
    "substantive": 80,
    "policy": 70,
    "law": 70,
    "drafting": 40,
    "grammar": 20,
    "fixup": 10,
}

MAX_POSITION = 10 ** 12

_CHANNEL_NORMALIZATION: Dict[str, str] = {
    "presence": "presence",
    "substantive": "substantive",
    "substance": "substantive",
    "policy": "policy",
    "law": "law",
    "legal": "law",
    "drafting": "drafting",
    "style": "drafting",
    "grammar": "grammar",
    "language": "grammar",
    "fixup": "fixup",
    "fix": "fixup",
    "cleanup": "fixup",
}

_META_CHANNEL_KEYS: Sequence[str] = (
    "channel",
    "agenda_channel",
)

_META_SALIENCE_KEYS: Sequence[str] = (
    "salience",
    "rule_salience",
)

_SPEC_KEYS: Sequence[str] = (
    "spec",
    "rule_spec",
    "rule",
)


def coerce_int(value: Any) -> int | None:
    """Best-effort coercion used for offsets and salience."""

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


def infer_channel(finding: Mapping[str, Any]) -> str:
    """Infer a channel when the finding does not provide one explicitly."""

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


def _normalize_group(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    return _CHANNEL_NORMALIZATION.get(lowered, lowered)


def _candidate_channels(finding: Mapping[str, Any]) -> Iterable[str]:
    explicit = finding.get("agenda_group")
    if isinstance(explicit, str) and explicit.strip():
        yield explicit

    channel = finding.get("channel")
    if isinstance(channel, str) and channel.strip():
        yield channel

    meta = finding.get("meta")
    if isinstance(meta, Mapping):
        for key in _META_CHANNEL_KEYS:
            candidate = meta.get(key)
            if isinstance(candidate, str) and candidate.strip():
                yield candidate

    for spec_key in _SPEC_KEYS:
        spec = finding.get(spec_key)
        if isinstance(spec, Mapping):
            candidate = spec.get("channel")
            if isinstance(candidate, str) and candidate.strip():
                yield candidate

    inferred = infer_channel(finding)
    if inferred:
        yield inferred


def map_to_agenda_group(finding: Mapping[str, Any]) -> str:
    """Map a finding to an agenda group used for prioritisation."""

    for candidate in _candidate_channels(finding):
        group = _normalize_group(candidate)
        if group:
            return group

    meta = finding.get("meta")
    if isinstance(meta, Mapping):
        presence_flag = meta.get("presence")
        if isinstance(presence_flag, bool) and presence_flag:
            return "presence"
        if isinstance(presence_flag, (int, float)) and presence_flag:
            return "presence"

    rule_id = finding.get("rule_id")
    if isinstance(rule_id, str) and rule_id.lower().startswith("presence_"):
        return "presence"

    return "substantive"


def _candidate_salience_values(finding: Mapping[str, Any]) -> Iterable[Any]:
    yield finding.get("salience")

    meta = finding.get("meta")
    if isinstance(meta, Mapping):
        for key in _META_SALIENCE_KEYS:
            value = meta.get(key)
            if value is not None:
                yield value

    for spec_key in _SPEC_KEYS:
        spec = finding.get(spec_key)
        if isinstance(spec, Mapping):
            value = spec.get("salience")
            if value is not None:
                yield value


def resolve_salience(
    finding: MutableMapping[str, Any],
    *,
    group: str | None = None,
) -> int:
    """Resolve the salience for ``finding`` clamped to [0, 100]."""

    for value in _candidate_salience_values(finding):
        coerced = coerce_int(value)
        if coerced is None:
            continue
        if coerced < 0:
            return 0
        if coerced > 100:
            return 100
        return coerced

    if group is None:
        group = map_to_agenda_group(finding)

    default = DEFAULT_SALIENCE.get(group, 50)
    return int(default)


def extract_span(finding: Mapping[str, Any]) -> Tuple[int, int] | None:
    """Extract a representative span from a finding if present."""

    start = coerce_int(finding.get("start"))
    end = coerce_int(finding.get("end"))
    if start is not None and end is not None:
        return start, end

    anchor = finding.get("anchor")
    if isinstance(anchor, Mapping):
        span = anchor.get("span")
        if isinstance(span, Sequence) and len(span) == 2:
            a_start = coerce_int(span[0])
            a_end = coerce_int(span[1])
            if a_start is not None and a_end is not None:
                return a_start, a_end
        a_start = coerce_int(anchor.get("start"))
        a_end = coerce_int(anchor.get("end"))
        if a_start is not None and a_end is not None:
            return a_start, a_end
        range_payload = anchor.get("range")
        if isinstance(range_payload, Mapping):
            a_start = coerce_int(range_payload.get("start"))
            a_end = coerce_int(range_payload.get("end"))
            if a_start is not None and a_end is not None:
                return a_start, a_end

    anchors = finding.get("anchors")
    if isinstance(anchors, Sequence):
        for candidate in anchors:
            if not isinstance(candidate, Mapping):
                continue
            span = candidate.get("span")
            if isinstance(span, Sequence) and len(span) == 2:
                a_start = coerce_int(span[0])
                a_end = coerce_int(span[1])
                if a_start is not None and a_end is not None:
                    return a_start, a_end
            a_start = coerce_int(candidate.get("start"))
            a_end = coerce_int(candidate.get("end"))
            if a_start is not None and a_end is not None:
                return a_start, a_end
            range_payload = candidate.get("range")
            if isinstance(range_payload, Mapping):
                a_start = coerce_int(range_payload.get("start"))
                a_end = coerce_int(range_payload.get("end"))
                if a_start is not None and a_end is not None:
                    return a_start, a_end

    span = finding.get("span")
    if isinstance(span, Mapping):
        a_start = coerce_int(span.get("start"))
        a_end = coerce_int(span.get("end"))
        if a_start is not None and a_end is not None:
            return a_start, a_end
        range_payload = span.get("range")
        if isinstance(range_payload, Mapping):
            a_start = coerce_int(range_payload.get("start"))
            a_end = coerce_int(range_payload.get("end"))
            if a_start is not None and a_end is not None:
                return a_start, a_end

    return None


def agenda_sort_key(
    finding: MutableMapping[str, Any],
    *,
    group: str | None = None,
    salience: int | None = None,
    start: int | None = None,
) -> Tuple[int, int, int, str]:
    """Compute the agenda-based sort key for a finding."""

    if group is None:
        group = map_to_agenda_group(finding)
    if salience is None:
        salience = resolve_salience(finding, group=group)
    if start is None:
        span = extract_span(finding)
        if span is not None:
            start = span[0]
    if start is None:
        start = MAX_POSITION

    agenda_rank = AGENDA_ORDER.get(group, max(AGENDA_ORDER.values()) + 1)
    rule_id = finding.get("rule_id") or ""
    return (
        agenda_rank,
        -int(salience),
        int(start),
        str(rule_id),
    )
