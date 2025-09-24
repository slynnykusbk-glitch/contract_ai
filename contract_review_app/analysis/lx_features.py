"""Lightweight L0 feature extraction for segments."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Mapping, Sequence

from contract_review_app.analysis.extractors import (
    extract_amounts,
    extract_dates,
    extract_durations,
    extract_incoterms,
    extract_jurisdiction,
    extract_law,
    extract_percentages,
)
from contract_review_app.analysis.labels_taxonomy import resolve_labels
from contract_review_app.core.lx_types import LxDocFeatures, LxFeatureSet


EntityExtractor = Callable[[str], Sequence[Mapping[str, Any]]]

_ENTITY_EXTRACTORS: Dict[str, EntityExtractor] = {
    "amounts": extract_amounts,
    "percentages": extract_percentages,
    "durations": extract_durations,
    "dates": extract_dates,
    "incoterms": extract_incoterms,
    "law": extract_law,
    "jurisdiction": extract_jurisdiction,
}

_ENTITY_LIMITS: Dict[str, int] = {
    "amounts": 20,
    "percentages": 20,
    "durations": 20,
    "dates": 20,
    "incoterms": 12,
    "law": 12,
    "jurisdiction": 12,
}

_DURATION_PATTERN = re.compile(r"^P(?P<number>\d+)(?P<unit>[DWMY])$", re.IGNORECASE)
_PAREN_NUMBER_RE = re.compile(r"\((\d+)\)")

_LEGACY_LABEL_ALIASES: Dict[str, tuple[str, ...]] = {
    "payment_terms": ("Payment",),
    "term": ("Term",),
    "limitation_of_liability": ("Liability",),
    "confidentiality": ("Confidentiality",),
    "indemnity_general": ("Indemnity",),
    "governing_law": ("GoverningLaw",),
    "jurisdiction": ("Jurisdiction",),
    "dispute_resolution": ("Dispute",),
    "ip_ownership": ("IP",),
    "notices": ("Notices",),
    "taxes": ("Taxes",),
    "set_off": ("SetOff",),
    "late_payment_interest": ("Interest",),
    "price_changes_indexation": ("Price",),
    "service_levels_sla": ("SLA",),
    "kpi": ("KPI",),
    "acceptance": ("Acceptance",),
    "boilerplate": ("Boilerplate",),
}


def _get_segment_value(segment: Any, key: str) -> Any:
    if isinstance(segment, Mapping):
        return segment.get(key)
    return getattr(segment, key, None)


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _normalize_duration_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        duration = value.get("duration") or value.get("iso")
    else:
        duration = value
    if not isinstance(duration, str):
        return _normalize_value(value)

    normalized: Dict[str, Any] = {"duration": duration}
    match = _DURATION_PATTERN.match(duration)
    if match:
        number = int(match.group("number"))
        unit_code = match.group("unit").upper()
        unit_map = {"D": "days", "W": "weeks", "M": "months", "Y": "years"}
        unit = unit_map.get(unit_code)
        if unit:
            normalized[unit] = number
    return normalized


def _normalize_entity_entry(name: str, item: Mapping[str, Any]) -> Mapping[str, Any]:
    entry: Dict[str, Any] = {}

    start = item.get("start")
    if isinstance(start, (int, float)):
        entry["start"] = int(start)

    end = item.get("end")
    if isinstance(end, (int, float)):
        entry["end"] = int(end)

    raw_value = item.get("value")
    if raw_value is not None:
        if name == "durations":
            normalized_value = _normalize_duration_value(raw_value)
        else:
            normalized_value = _normalize_value(raw_value)
        if normalized_value is not None:
            entry["value"] = normalized_value

    kind = item.get("kind")
    if name == "amounts" and (kind in (None, "")):
        currency = None
        if isinstance(raw_value, Mapping):
            currency = raw_value.get("currency")
        if isinstance(currency, str) and currency:
            entry["kind"] = currency
    elif isinstance(kind, str) and kind:
        entry["kind"] = kind
    elif kind not in (None, ""):
        entry["kind"] = str(kind)

    return entry


def _normalize_parenthetical_numbers(text: str) -> str:
    return _PAREN_NUMBER_RE.sub(lambda m: f" {m.group(1)} ", text)


def _summarize_amounts(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    summary: list[str] = []
    for entry in entries:
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        currency = value.get("currency")
        amount = value.get("amount")
        if isinstance(currency, str) and amount is not None:
            summary.append(f"{currency} {amount}")
    return summary[: _ENTITY_LIMITS["amounts"]]


def _summarize_durations(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for entry in entries:
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        duration = value.get("duration")
        if not isinstance(duration, str):
            continue
        match = _DURATION_PATTERN.match(duration)
        if not match:
            continue
        number = int(match.group("number"))
        unit_code = match.group("unit").upper()
        unit_map = {"D": "days", "W": "weeks", "M": "months", "Y": "years"}
        unit = unit_map.get(unit_code)
        if unit and unit not in summary:
            summary[unit] = number
    return summary


def _summarize_law_signals(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    signals: list[str] = []
    for entry in entries:
        value = entry.get("value")
        if isinstance(value, Mapping):
            code = value.get("code")
            if isinstance(code, str) and code:
                signals.append(code)
    return signals


def _summarize_jurisdiction(entries: Sequence[Mapping[str, Any]]) -> str | None:
    for entry in entries:
        value = entry.get("value")
        if isinstance(value, Mapping):
            code = value.get("code")
            if isinstance(code, str) and code:
                return code
    return None


def _collect_segment_entities(text: str) -> Dict[str, list[Mapping[str, Any]]]:
    entities: Dict[str, list[Mapping[str, Any]]] = {}
    text_variants = [text]
    normalized = _normalize_parenthetical_numbers(text)
    if normalized != text:
        text_variants.append(normalized)

    for name, extractor in _ENTITY_EXTRACTORS.items():
        limit = _ENTITY_LIMITS.get(name, 20)
        seen_spans: set[tuple[int, int]] = set()
        collected: list[Mapping[str, Any]] = []
        for variant in text_variants:
            try:
                extracted = extractor(variant)
            except Exception:
                extracted = []
            for item in extracted:
                if not isinstance(item, Mapping):
                    continue
                normalized_entry = _normalize_entity_entry(name, item)
                if not normalized_entry:
                    continue
                start = normalized_entry.get("start")
                end = normalized_entry.get("end")
                span = None
                if isinstance(start, int) and isinstance(end, int):
                    span = (start, end)
                    if span in seen_spans:
                        continue
                    seen_spans.add(span)
                collected.append(normalized_entry)
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break
        if collected:
            entities[name] = collected
    return entities


def _coerce_heading(raw_heading: Any) -> str | None:
    if raw_heading in (None, ""):
        return None
    return str(raw_heading)


def extract_l0_features(doc: Any, segments: Sequence[Any]) -> LxDocFeatures:
    """Extract lightweight features for TRACE and dispatcher usage."""

    by_segment: Dict[int, LxFeatureSet] = {}

    for segment in segments or []:
        raw_id = _get_segment_value(segment, "id")
        try:
            seg_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        seg_text = _get_segment_value(segment, "text") or ""
        seg_heading = _coerce_heading(_get_segment_value(segment, "heading"))

        text = str(seg_text or "")
        resolved = resolve_labels(text, seg_heading)
        legacy_labels: set[str] = set()
        for label in resolved:
            legacy_labels.update(_LEGACY_LABEL_ALIASES.get(label, ()))
        labels = sorted({*resolved, *legacy_labels})
        entities = _collect_segment_entities(text)

        feature_set = LxFeatureSet()
        feature_set.labels = labels
        feature_set.entities = entities
        feature_set.amounts = _summarize_amounts(entities.get("amounts", []))
        feature_set.durations = _summarize_durations(entities.get("durations", []))
        feature_set.law_signals = _summarize_law_signals(entities.get("law", []))
        feature_set.jurisdiction = _summarize_jurisdiction(
            entities.get("jurisdiction", [])
        )

        by_segment[seg_id] = feature_set

    return LxDocFeatures(by_segment=by_segment)


__all__ = ["extract_l0_features", "LxDocFeatures", "LxFeatureSet"]
