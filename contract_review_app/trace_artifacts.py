from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable, Mapping, Sequence, TYPE_CHECKING

from contract_review_app.intake.parser import ParsedDocument

from .types_trace import TConstraints, TDispatch, TFeatures, TProposals


MAX_LABELS_PER_SEG = 16
MAX_AMOUNTS_PER_SEG = 20
MAX_DURATIONS_PER_SEG = 20

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from contract_review_app.core.lx_types import LxDocFeatures, LxFeatureSet

def _coerce_labels(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.strip()
        return [raw] if raw else []
    if isinstance(raw, Mapping):
        return [
            str(v).strip()
            for v in raw.values()
            if v not in (None, "") and str(v).strip()
        ]
    if isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray, str)):
        values: list[str] = []
        for item in raw:
            if item is None:
                continue
            if isinstance(item, str):
                item = item.strip()
                if not item:
                    continue
                values.append(item)
            else:
                text = str(item).strip()
                if text:
                    values.append(text)
        return values
    text = str(raw).strip()
    return [text] if text else []


def _resolve_language(doc_norm: ParsedDocument) -> str:
    lang = getattr(doc_norm, "language", None)
    if isinstance(lang, str) and lang:
        return lang
    segments = getattr(doc_norm, "segments", None) or []
    for seg in segments:
        if isinstance(seg, Mapping):
            seg_lang = seg.get("lang")
            if isinstance(seg_lang, str) and seg_lang:
                return seg_lang
    return "und"


def _unique_ordered(items: Iterable[str]) -> list[str]:
    ordered: dict[str, None] = {}
    for item in items:
        if item not in ordered:
            ordered[item] = None
    return list(ordered.keys())


def _flatten_to_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, Mapping):
        items: list[str] = []
        for entry in value.values():
            items.extend(_flatten_to_strings(entry))
        return items
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        items: list[str] = []
        for entry in value:
            items.extend(_flatten_to_strings(entry))
        return items
    text = str(value).strip()
    return [text] if text else []


def _collect_amounts(*values: Any) -> list[str]:
    collected: list[str] = []
    for value in values:
        collected.extend(_flatten_to_strings(value))
    unique = _unique_ordered(collected)
    return unique[:MAX_AMOUNTS_PER_SEG]


def _coerce_duration_value(value: Any) -> list[dict[str, int]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        entry: dict[str, int] = {}
        for key, raw_val in value.items():
            try:
                entry[str(key)] = int(raw_val)
            except (TypeError, ValueError):
                continue
        return [entry] if entry else []
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        items: list[dict[str, int]] = []
        for part in value:
            items.extend(_coerce_duration_value(part))
        return items
    return []


def _collect_duration_entries(*values: Any) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    for value in values:
        entries.extend(_coerce_duration_value(value))
    deduped: list[dict[str, int]] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    for entry in entries:
        if not entry:
            continue
        key = tuple(sorted(entry.items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
        if len(deduped) >= MAX_DURATIONS_PER_SEG:
            break
    return deduped


def _slice_normalized_text(norm_text: str, start: int, end: int) -> str:
    if not norm_text:
        return ""
    length = len(norm_text)
    start = max(0, min(start, length))
    end = max(start, min(end, length))
    return norm_text[start:end]


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return sum(1 for token in text.split() if token)


def _normalize_hints(hints: Any) -> list[Any]:
    if hints is None:
        return []
    if isinstance(hints, str):
        return [hints]
    if isinstance(hints, Mapping):
        return [hints]
    try:
        return list(hints)
    except TypeError:
        return [hints]


def serialize_features(
    doc_norm: ParsedDocument,
    segments: Iterable[Mapping[str, Any]],
    l0_features: "LxDocFeatures | None" = None,
) -> TFeatures:
    norm_text = getattr(doc_norm, "normalized_text", "") or ""
    doc_hash = sha256(norm_text.encode("utf-8")).hexdigest()

    doc_payload: dict[str, Any] = {
        "language": _resolve_language(doc_norm),
        "length": len(norm_text),
        "hash": doc_hash,
    }

    features_by_segment: Mapping[int, "LxFeatureSet"] = {}
    if l0_features is not None:
        features_by_segment = getattr(l0_features, "by_segment", {}) or {}

    segment_entries = []
    for seg in segments or []:
        if isinstance(seg, Mapping):
            seg_id = seg.get("id")
            start_raw = seg.get("start", 0)
            end_raw = seg.get("end", 0)
            clause_type = seg.get("clause_type")
            labels_raw = seg.get("labels")
            entities_raw = seg.get("entities") or {}
        else:
            seg_id = getattr(seg, "id", None)
            start_raw = getattr(seg, "start", 0)
            end_raw = getattr(seg, "end", 0)
            clause_type = getattr(seg, "clause_type", None)
            labels_raw = getattr(seg, "labels", None)
            entities_raw = getattr(seg, "entities", {}) or {}

        try:
            seg_id_int = int(seg_id) if seg_id is not None else None
        except (TypeError, ValueError):  # pragma: no cover - defensive
            seg_id_int = None

        try:
            start = int(start_raw)
        except (TypeError, ValueError):
            start = 0
        try:
            end = int(end_raw)
        except (TypeError, ValueError):
            end = 0

        segment_labels: list[str] = []
        segment_labels.extend(_coerce_labels(clause_type))
        segment_labels.extend(_coerce_labels(labels_raw))

        feat_obj = None
        if (
            seg_id_int is not None
            and isinstance(features_by_segment, Mapping)
            and seg_id_int in features_by_segment
        ):
            feat_obj = features_by_segment.get(seg_id_int)
            if feat_obj is not None:
                segment_labels.extend(_coerce_labels(getattr(feat_obj, "labels", None)))

        labels = sorted({label for label in segment_labels if label})
        if len(labels) > MAX_LABELS_PER_SEG:
            labels = labels[:MAX_LABELS_PER_SEG]

        normalized_span = _slice_normalized_text(norm_text, start, end)
        token_len = _count_tokens(normalized_span)

        if isinstance(entities_raw, Mapping):
            entities_dict: dict[str, Any] = {
                str(k): v
                for k, v in entities_raw.items()
                if k not in {"amounts", "durations"} and v not in (None, "", [], {})
            }
            amounts_raw = entities_raw.get("amounts")
            durations_raw = entities_raw.get("durations")
        else:
            entities_dict = {}
            amounts_raw = None
            durations_raw = None

        amounts_sources = [amounts_raw]
        durations_sources = [durations_raw]

        if feat_obj is not None:
            amounts_sources.append(getattr(feat_obj, "amounts", None))
            durations_sources.append(getattr(feat_obj, "durations", None))

        amounts = _collect_amounts(*amounts_sources)
        if amounts:
            entities_dict["amounts"] = amounts

        durations = _collect_duration_entries(*durations_sources)
        if durations:
            entities_dict["durations"] = durations

        segment_entries.append(
            {
                "id": seg_id_int if seg_id_int is not None else seg_id,
                "range": {"start": start, "end": end},
                "labels": labels,
                "entities": entities_dict,
                "tokens": {"len": token_len},
            }
        )

    return {
        "doc": doc_payload,
        "segments": segment_entries,
    }


def build_features(
    doc_norm: ParsedDocument,
    segments: Iterable[Mapping[str, Any]],
    l0_features: "LxDocFeatures | None" = None,
    hints: Any = None,
) -> TFeatures:
    payload = serialize_features(doc_norm, segments, l0_features)
    doc_payload = payload.setdefault("doc", {})
    doc_payload["hints"] = _normalize_hints(hints)
    return payload

def _coerce_match_entry(item: Any) -> Mapping[str, Any]:
    start = None
    end = None
    text = None

    if isinstance(item, Mapping):
        start = item.get("start")
        end = item.get("end")
        text = item.get("text")
    else:
        start = getattr(item, "start", None)
        end = getattr(item, "end", None)
        text = getattr(item, "text", None)

    payload: dict[str, Any] = {}
    if isinstance(start, (int, float)):
        payload["start"] = int(start)
    if isinstance(end, (int, float)):
        payload["end"] = int(end)
    if text is not None:
        payload["text"] = str(text)
    return payload


def _extract_gate_value(gates: Any, key: str) -> Any:
    if isinstance(gates, Mapping):
        return gates.get(key)
    return getattr(gates, key, None)


def build_dispatch(
    rules_loaded: int,
    evaluated: int,
    triggered: int,
    candidates_iter: Iterable[Any],
) -> TDispatch:
    candidates_payload: list[dict[str, Any]] = []

    for candidate in candidates_iter or []:
        if isinstance(candidate, Mapping):
            rule_id = candidate.get("rule_id")
            gates = candidate.get("gates")
            gates_passed = candidate.get("gates_passed")
            expected_any = candidate.get("expected_any")
            matched_entries = candidate.get("matched") or []
            reason = candidate.get("reason_not_triggered")
        else:
            rule_id = getattr(candidate, "rule_id", None)
            gates = getattr(candidate, "gates", None)
            gates_passed = getattr(candidate, "gates_passed", None)
            expected_any = getattr(candidate, "expected_any", None)
            matched_entries = getattr(candidate, "matched", [])
            reason = getattr(candidate, "reason", None)

        gates_payload = {
            "packs": _extract_gate_value(gates, "packs"),
            "lang": _extract_gate_value(gates, "lang"),
            "doctype": (
                _extract_gate_value(gates, "doctype")
                if _extract_gate_value(gates, "doctype") is not None
                else _extract_gate_value(gates, "doctypes")
            ),
        }

        matches: Sequence[Any]
        if isinstance(matched_entries, Sequence) and not isinstance(
            matched_entries, (str, bytes, bytearray)
        ):
            matches = matched_entries
        else:
            matches = []

        candidates_payload.append(
            {
                "rule_id": str(rule_id) if rule_id is not None else "",
                "gates": gates_payload,
                "gates_passed": bool(gates_passed),
                "triggers": {
                    "expected_any": list(expected_any or []),
                    "matched": [
                        _coerce_match_entry(entry)
                        for entry in matches
                        if entry is not None
                    ],
                },
                "reason_not_triggered": str(reason)
                if reason is not None
                else None,
            }
        )

    return {
        "ruleset": {
            "loaded": int(rules_loaded),
            "evaluated": int(evaluated),
            "triggered": int(triggered),
        },
        "candidates": candidates_payload,
    }


def _coerce_check_details(details: Any) -> dict[str, Any]:
    if details is None:
        return {}
    if isinstance(details, Mapping):
        return {str(k): v for k, v in details.items()}
    if hasattr(details, "model_dump"):
        try:
            dumped = details.model_dump(exclude_none=True)  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return {str(k): v for k, v in dumped.items()}
        except Exception:
            pass
    if hasattr(details, "dict"):
        try:
            dumped = details.dict()  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return {str(k): v for k, v in dumped.items()}
        except Exception:
            pass
    return {"value": details}


def build_constraints(checks_iter: Iterable[Any]) -> TConstraints:
    checks_payload: list[dict[str, Any]] = []
    for entry in checks_iter or []:
        if entry is None:
            continue
        if isinstance(entry, Mapping):
            raw_id = entry.get("id")
            raw_scope = entry.get("scope")
            raw_result = entry.get("result")
            raw_details = entry.get("details")
        else:
            raw_id = getattr(entry, "id", None)
            raw_scope = getattr(entry, "scope", None)
            raw_result = getattr(entry, "result", None)
            raw_details = getattr(entry, "details", None)

        check_id = str(raw_id) if raw_id is not None else ""
        scope = str(raw_scope) if raw_scope is not None else ""
        result = str(raw_result or "").lower()
        if result not in {"pass", "fail", "skip"}:
            result = "skip"
        details = _coerce_check_details(raw_details)

        checks_payload.append(
            {
                "id": check_id,
                "scope": scope,
                "result": result,  # type: ignore[typeddict-item]
                "details": details,
            }
        )

    return {"checks": checks_payload}


def _extract_field(item: Any, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_ops(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, bytearray)):
        return list(raw)
    return [raw]


def build_proposals(
    drafts_iter: Iterable[Any] | None = None,
    merged_iter: Iterable[Any] | None = None,
) -> TProposals:
    drafts_payload: list[dict[str, Any]] = []
    for draft in drafts_iter or []:
        rule_id = _extract_field(draft, "rule_id")
        if rule_id is None:
            continue
        ops = _normalize_ops(_extract_field(draft, "ops"))
        before = _extract_field(draft, "before")
        snippet = _extract_field(draft, "snippet")
        after = _extract_field(draft, "after")
        if before is None:
            before = snippet
        drafts_payload.append(
            {
                "rule_id": rule_id,
                "ops": ops,
                "before": before,
                "after": after,
            }
        )

    merged_payload: list[dict[str, Any]] = []
    for item in merged_iter or []:
        rule_id = _extract_field(item, "rule_id")
        if rule_id is None:
            continue
        ops = _normalize_ops(_extract_field(item, "ops"))
        text = _extract_field(item, "text")
        if text is None:
            text = _extract_field(item, "after")
        if text is None:
            text = _extract_field(item, "snippet")
        merged_payload.append(
            {
                "rule_id": rule_id,
                "ops": ops,
                "text": text,
            }
        )

    return {"drafts": drafts_payload, "merged": merged_payload}
