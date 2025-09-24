"""Coverage map loader and coverage computation helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

import yaml
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ConfigDict,
    field_validator,
    model_validator,
)

from contract_review_app.legal_rules.dispatcher import _normalize_token

logger = logging.getLogger(__name__)

COVERAGE_MAP_PATH = Path(__file__).with_name("coverage_map.yaml")

ZONE_ALIASES: Dict[str, List[str]] = {
    "governing_law": ["law", "governed_by"],
    "dispute_resolution": ["dr", "dispute"],
}

ENTITY_KEYS = ("amounts", "durations", "law", "jurisdiction")

COVERAGE_MAX_DETAILS = 50
COVERAGE_MAX_SEGMENTS_PER_ZONE = 3


def _coerce_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, Mapping):
        items: List[str] = []
        for entry in value.values():
            items.extend(_coerce_str_list(entry))
        return items
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        items: List[str] = []
        for entry in value:
            items.extend(_coerce_str_list(entry))
        return items
    text = str(value).strip()
    return [text] if text else []


class LabelSelectorsSchema(BaseModel):
    any: List[str] = Field(default_factory=list)
    all: List[str] = Field(default_factory=list)
    none: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("any", "all", "none", mode="before")
    @classmethod
    def _clean_selectors(cls, value: Any) -> List[str]:
        return _coerce_str_list(value)


class EntitySelectorsSchema(BaseModel):
    amounts: bool = False
    durations: bool = False
    law: bool = False
    jurisdiction: bool = False

    model_config = ConfigDict(extra="forbid")


class CoverageZoneSchema(BaseModel):
    zone_id: str
    zone_name: str
    description: Optional[str] = None
    label_selectors: LabelSelectorsSchema
    entity_selectors: EntitySelectorsSchema = Field(
        default_factory=EntitySelectorsSchema
    )
    rule_ids_opt: List[str] = Field(default_factory=list)
    weight: Optional[float] = None
    required: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("zone_id", mode="before")
    @classmethod
    def _ensure_zone_id(cls, value: Any) -> str:
        values = _coerce_str_list(value)
        if not values:
            raise ValueError("zone_id is required")
        return values[0]

    @field_validator("zone_name", mode="before")
    @classmethod
    def _ensure_zone_name(cls, value: Any) -> str:
        values = _coerce_str_list(value)
        if not values:
            raise ValueError("zone_name is required")
        return values[0]

    @field_validator("rule_ids_opt", mode="before")
    @classmethod
    def _ensure_rule_ids(cls, value: Any) -> List[str]:
        items = _coerce_str_list(value)
        seen: Set[str] = set()
        deduped: List[str] = []
        for item in items:
            key = str(item).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped


class CoverageMapSchema(BaseModel):
    version: int
    zones: List[CoverageZoneSchema]

    model_config = ConfigDict(extra="forbid")

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, value: Any) -> int:
        if value is None:
            raise ValueError("version is required")
        try:
            version_int = int(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            raise ValueError("version must be an integer") from None
        if version_int < 1:
            raise ValueError("version must be >= 1")
        return version_int

    @model_validator(mode="after")
    def _check_unique_zone_ids(self) -> "CoverageMapSchema":
        seen: Set[str] = set()
        for zone in self.zones or []:
            zone_id = zone.zone_id
            if zone_id in seen:
                raise ValueError(f"duplicate zone_id: {zone_id}")
            seen.add(zone_id)
        return self


@dataclass(frozen=True)
class CoverageZone:
    zone_id: str
    zone_name: str
    description: Optional[str]
    label_any: Set[str] = field(default_factory=set)
    label_all: Set[str] = field(default_factory=set)
    label_none: Set[str] = field(default_factory=set)
    entity_selectors: Dict[str, bool] = field(default_factory=dict)
    rule_ids: Set[str] = field(default_factory=set)
    weight: Optional[float] = None
    required: bool = False


@dataclass(frozen=True)
class LoadedCoverageMap:
    version: int
    zones: Sequence[CoverageZone]
    label_index: Dict[str, Set[str]]
    rule_index: Dict[str, Set[str]]


def _normalize_label(label: str) -> str:
    token = _normalize_token(str(label)) if label is not None else ""
    return token.strip("_")


def _expand_with_aliases(label: str) -> Set[str]:
    normalized = _normalize_label(label)
    if not normalized:
        return set()
    expanded: Set[str] = {normalized}
    for alias in ZONE_ALIASES.get(normalized, []):
        alias_norm = _normalize_label(alias)
        if alias_norm:
            expanded.add(alias_norm)
    return expanded


def _normalize_selector_values(values: Iterable[str]) -> Set[str]:
    normalized: Set[str] = set()
    for value in values:
        normalized.update(_expand_with_aliases(value))
    return normalized


def _build_zone(schema: CoverageZoneSchema) -> CoverageZone:
    label_any = _normalize_selector_values(schema.label_selectors.any)
    label_all = _normalize_selector_values(schema.label_selectors.all)
    label_none = _normalize_selector_values(schema.label_selectors.none)

    entity_selectors = {
        key: bool(getattr(schema.entity_selectors, key)) for key in ENTITY_KEYS
    }

    rule_ids = {rid for rid in schema.rule_ids_opt}

    return CoverageZone(
        zone_id=schema.zone_id,
        zone_name=schema.zone_name,
        description=schema.description,
        label_any=label_any,
        label_all=label_all,
        label_none=label_none,
        entity_selectors=entity_selectors,
        rule_ids=rule_ids,
        weight=schema.weight,
        required=bool(schema.required),
    )


def _build_indexes(
    zones: Sequence[CoverageZone],
) -> tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    label_index: Dict[str, Set[str]] = {}
    rule_index: Dict[str, Set[str]] = {}
    for zone in zones:
        for label in zone.label_any.union(zone.label_all):
            if not label:
                continue
            label_index.setdefault(label, set()).add(zone.zone_id)
        for rule_id in zone.rule_ids:
            rule_index.setdefault(rule_id, set()).add(zone.zone_id)
    return label_index, rule_index


@lru_cache(maxsize=1)
def load_coverage_map() -> Optional[LoadedCoverageMap]:
    try:
        raw_text = COVERAGE_MAP_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - IO failure path
        logger.warning("Failed to read coverage map: %s", exc)
        return None

    try:
        raw_payload = yaml.safe_load(raw_text) or {}
        schema = CoverageMapSchema.model_validate(raw_payload)
    except ValidationError as exc:
        logger.warning("Coverage map validation failed: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover - YAML failure
        logger.warning("Failed to parse coverage map: %s", exc)
        return None

    zones = tuple(_build_zone(zone) for zone in schema.zones)
    label_index, rule_index = _build_indexes(zones)

    return LoadedCoverageMap(
        version=schema.version,
        zones=zones,
        label_index=label_index,
        rule_index=rule_index,
    )


def invalidate_cache() -> None:
    load_coverage_map.cache_clear()


def _normalize_segment_labels(labels: Iterable[str]) -> Set[str]:
    normalized: Set[str] = set()
    for label in labels or []:
        normalized.update(_expand_with_aliases(label))
    return normalized


def _extract_entities_count(entities: Mapping[str, Any] | None, key: str) -> int:
    if not entities or key not in entities:
        return 0
    value = entities.get(key)
    if isinstance(value, Mapping):
        if hasattr(value, "values"):
            try:
                return len(list(value.values()))
            except Exception:
                return len(list(value))
        try:
            return len(value)
        except Exception:
            return 0
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return 0


def _coerce_span(span: Any) -> Optional[List[int]]:
    if isinstance(span, Mapping):
        start = span.get("start")
        end = span.get("end")
        if end is None and "length" in span and start is not None:
            try:
                length = int(span.get("length"))
            except (TypeError, ValueError):
                length = None
            if length is not None:
                try:
                    start_int = int(start)
                    end = start_int + max(length, 0)
                except (TypeError, ValueError):
                    end = None
        if start is not None and end is not None:
            try:
                return [int(start), int(end)]
            except (TypeError, ValueError):
                return None
    if isinstance(span, Sequence) and len(span) >= 2:
        try:
            start = int(span[0])
            end = int(span[1])
        except (TypeError, ValueError):
            return None
        return [start, end]
    return None


def _segment_span(segment: Any) -> Optional[List[int]]:
    span = None
    if isinstance(segment, Mapping):
        span = segment.get("span")
        if span is None:
            start = segment.get("start")
            end = segment.get("end")
            if start is not None and end is not None:
                span = [start, end]
    else:
        span = getattr(segment, "span", None)
    return _coerce_span(span)


def _segment_labels(segment: Any) -> Iterable[str]:
    if isinstance(segment, Mapping):
        return segment.get("labels") or []
    return getattr(segment, "labels", []) or []


def _segment_entities(segment: Any) -> Mapping[str, Any]:
    if isinstance(segment, Mapping):
        entities = segment.get("entities")
    else:
        entities = getattr(segment, "entities", None)
    if isinstance(entities, Mapping):
        return entities
    return {}


def _segment_index(segment: Any, default: int) -> int:
    if isinstance(segment, Mapping):
        if "index" in segment:
            try:
                return int(segment["index"])
            except (TypeError, ValueError):
                return default
        if "segment_id" in segment:
            try:
                return int(segment["segment_id"])
            except (TypeError, ValueError):
                return default
    if hasattr(segment, "index"):
        try:
            return int(getattr(segment, "index"))
        except (TypeError, ValueError):
            return default
    return default


def _sanitize_rule_list(
    rules: Iterable[str], rule_lookup: Mapping[str, Any]
) -> List[str]:
    seen: Set[str] = set()
    sanitized: List[str] = []
    for rule in rules:
        key = str(rule).strip()
        if not key or key in seen:
            continue
        if rule_lookup and key not in rule_lookup:
            continue
        seen.add(key)
        sanitized.append(key)
    return sanitized


def sanitize_coverage_payload(
    payload: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    details_raw = list(payload.get("details", []) or [])
    sanitized_details: List[Dict[str, Any]] = []
    for detail in details_raw[:COVERAGE_MAX_DETAILS]:
        if not isinstance(detail, Mapping):
            continue
        zone_id = detail.get("zone_id")
        status = detail.get("status")
        if not isinstance(zone_id, str) or not isinstance(status, str):
            continue
        matched_labels = [
            str(lbl)
            for lbl in detail.get("matched_labels", []) or []
            if str(lbl).strip()
        ]
        matched_entities_raw = detail.get("matched_entities")
        matched_entities: Dict[str, int] = {}
        if isinstance(matched_entities_raw, Mapping):
            for key in ENTITY_KEYS:
                try:
                    matched_entities[key] = int(matched_entities_raw.get(key, 0))
                except (TypeError, ValueError):
                    matched_entities[key] = 0
        segments_sanitized: List[Dict[str, Any]] = []
        for segment in (detail.get("segments") or [])[:COVERAGE_MAX_SEGMENTS_PER_ZONE]:
            if not isinstance(segment, Mapping):
                continue
            segment_index = segment.get("index")
            if not isinstance(segment_index, int):
                try:
                    segment_index = int(segment_index)
                except (TypeError, ValueError):
                    segment_index = None
            span = (
                _coerce_span(segment.get("span"))
                if isinstance(segment, Mapping)
                else None
            )
            if segment_index is None or span is None:
                continue
            segments_sanitized.append({"index": segment_index, "span": span})
        candidate_rules = [
            str(rule)
            for rule in detail.get("candidate_rules", []) or []
            if str(rule).strip()
        ]
        fired_rules = [
            str(rule)
            for rule in detail.get("fired_rules", []) or []
            if str(rule).strip()
        ]
        missing_rules = [
            str(rule)
            for rule in detail.get("missing_rules", []) or []
            if str(rule).strip()
        ]
        sanitized_details.append(
            {
                "zone_id": zone_id,
                "status": status,
                "matched_labels": matched_labels,
                "matched_entities": matched_entities,
                "segments": segments_sanitized,
                "candidate_rules": candidate_rules,
                "fired_rules": fired_rules,
                "missing_rules": missing_rules,
            }
        )
    sanitized_payload: Dict[str, Any] = {
        "version": int(payload.get("version", 0) or 0),
        "zones_total": int(payload.get("zones_total", 0) or 0),
        "zones_present": int(payload.get("zones_present", 0) or 0),
        "zones_candidates": int(payload.get("zones_candidates", 0) or 0),
        "zones_fired": int(payload.get("zones_fired", 0) or 0),
        "details": sanitized_details,
    }
    return sanitized_payload


def build_coverage(
    segments: Sequence[Any],
    dispatch_candidates_by_segment: Sequence[Iterable[str] | Set[str]],
    triggered_rule_ids: Iterable[str],
    rule_lookup: Mapping[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    coverage_map = load_coverage_map()
    if coverage_map is None:
        return None

    if not segments:
        return sanitize_coverage_payload(
            {
                "version": coverage_map.version,
                "zones_total": len(coverage_map.zones),
                "zones_present": 0,
                "zones_candidates": 0,
                "zones_fired": 0,
                "details": [],
            }
        )

    normalized_triggered: Set[str] = {
        str(rule).strip() for rule in triggered_rule_ids if str(rule).strip()
    }
    valid_rule_lookup: Dict[str, Any] = {}
    if isinstance(rule_lookup, Mapping):
        for key, value in rule_lookup.items():
            if key:
                valid_rule_lookup[str(key)] = value

    zone_states: Dict[str, Dict[str, Any]] = {}
    for zone in coverage_map.zones:
        zone_states[zone.zone_id] = {
            "zone": zone,
            "status": "missing",
            "matched_labels": set(),
            "matched_entities": {key: 0 for key in ENTITY_KEYS},
            "segments": [],
            "candidate_rules": set(),
            "fired_rules": set(),
        }

    for idx, segment in enumerate(segments):
        segment_labels = _normalize_segment_labels(_segment_labels(segment))
        span = _segment_span(segment)
        entities = _segment_entities(segment)
        segment_index = _segment_index(segment, idx)
        candidates: Set[str] = set()
        if idx < len(dispatch_candidates_by_segment):
            raw_candidates = dispatch_candidates_by_segment[idx]
            if isinstance(raw_candidates, Mapping):
                raw_candidates = raw_candidates.keys()
            for candidate in raw_candidates or []:
                candidate_id = str(candidate).strip()
                if candidate_id:
                    candidates.add(candidate_id)

        for zone in coverage_map.zones:
            state = zone_states[zone.zone_id]
            if zone.label_any and not zone.label_any.intersection(segment_labels):
                continue
            if zone.label_all and not zone.label_all.issubset(segment_labels):
                continue
            if zone.label_none and zone.label_none.intersection(segment_labels):
                continue

            state["status"] = "present"
            matched_labels = zone.label_any.union(zone.label_all).intersection(
                segment_labels
            )
            if matched_labels:
                state["matched_labels"].update(sorted(matched_labels))

            if (
                span is not None
                and len(state["segments"]) < COVERAGE_MAX_SEGMENTS_PER_ZONE
            ):
                state["segments"].append({"index": segment_index, "span": span})

            for key in ENTITY_KEYS:
                if zone.entity_selectors.get(key):
                    state["matched_entities"][key] += _extract_entities_count(
                        entities, key
                    )

            if zone.rule_ids:
                matched_candidates = {rid for rid in candidates if rid in zone.rule_ids}
            else:
                matched_candidates = set(candidates)
            if matched_candidates:
                state["candidate_rules"].update(matched_candidates)
                if state["status"] != "rules_fired":
                    state["status"] = "rules_candidate"

    triggered_zone_rules: Dict[str, Set[str]] = {}
    for rule_id in normalized_triggered:
        zones_for_rule = coverage_map.rule_index.get(rule_id, set())
        for zone_id in zones_for_rule:
            triggered_zone_rules.setdefault(zone_id, set()).add(rule_id)

    details: List[Dict[str, Any]] = []
    zones_present = 0
    zones_candidates = 0
    zones_fired = 0

    for zone in coverage_map.zones:
        state = zone_states[zone.zone_id]
        status = state["status"]
        fired_rules: Set[str]
        if zone.rule_ids:
            fired_rules = zone.rule_ids.intersection(normalized_triggered)
        else:
            fired_rules = triggered_zone_rules.get(zone.zone_id, set())
        if fired_rules:
            status = "rules_fired"
            state["status"] = status
            state["fired_rules"].update(fired_rules)

        if status in {"present", "rules_candidate", "rules_fired"}:
            zones_present += 1
        if status in {"rules_candidate", "rules_fired"}:
            zones_candidates += 1
        if status == "rules_fired":
            zones_fired += 1

        if status == "missing":
            continue

        matched_labels = sorted(state["matched_labels"])
        matched_entities = state["matched_entities"]
        candidate_rules = _sanitize_rule_list(
            state["candidate_rules"], valid_rule_lookup
        )
        fired_rules_list = _sanitize_rule_list(state["fired_rules"], valid_rule_lookup)
        missing_rules = []
        if zone.rule_ids:
            missing_rules = _sanitize_rule_list(
                (zone.rule_ids - set(fired_rules_list)), valid_rule_lookup
            )

        details.append(
            {
                "zone_id": zone.zone_id,
                "status": status,
                "matched_labels": matched_labels,
                "matched_entities": matched_entities,
                "segments": state["segments"][:COVERAGE_MAX_SEGMENTS_PER_ZONE],
                "candidate_rules": candidate_rules,
                "fired_rules": fired_rules_list,
                "missing_rules": missing_rules,
            }
        )

        if len(details) >= COVERAGE_MAX_DETAILS:
            break

    payload = {
        "version": coverage_map.version,
        "zones_total": len(coverage_map.zones),
        "zones_present": zones_present,
        "zones_candidates": zones_candidates,
        "zones_fired": zones_fired,
        "details": details,
    }
    return sanitize_coverage_payload(payload)
