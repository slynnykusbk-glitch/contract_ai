from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, TYPE_CHECKING

from contract_review_app.intake.parser import ParsedDocument

from .types_trace import TConstraints, TDispatch, TFeatures, TProposals

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from contract_review_app.core.lx_types import LxDocFeatures, LxFeatureSet

def _coerce_labels(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.strip()
        return [raw] if raw else []
    if isinstance(raw, Mapping):
        return [str(v) for v in raw.values() if v is not None]
    if isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray)):
        return [str(item) for item in raw if item is not None]
    return [str(raw)]


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


def serialize_features(
    doc_norm: ParsedDocument,
    segments: Iterable[Mapping[str, Any]],
    l0_features: "LxDocFeatures | None" = None,
) -> TFeatures:
    norm_text = getattr(doc_norm, "normalized_text", "") or ""
    doc_hash = getattr(doc_norm, "checksum", None)
    if doc_hash is None:
        doc_hash = getattr(doc_norm, "checksum_sha256", None)

    doc_payload: dict[str, Any] = {
        "language": _resolve_language(doc_norm),
        "length": len(norm_text),
    }
    if doc_hash:
        doc_payload["hash"] = doc_hash

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
            seg_text = seg.get("text") or ""
        else:
            seg_id = getattr(seg, "id", None)
            start_raw = getattr(seg, "start", 0)
            end_raw = getattr(seg, "end", 0)
            clause_type = getattr(seg, "clause_type", None)
            labels_raw = getattr(seg, "labels", None)
            entities_raw = getattr(seg, "entities", {}) or {}
            seg_text = getattr(seg, "text", "") or ""

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

        labels = _coerce_labels(clause_type)
        if not labels:
            labels = _coerce_labels(labels_raw)

        if (
            seg_id_int is not None
            and isinstance(features_by_segment, Mapping)
            and seg_id_int in features_by_segment
        ):
            feat_obj = features_by_segment.get(seg_id_int)
            if feat_obj is not None:
                extra_labels = _coerce_labels(getattr(feat_obj, "labels", None))
                if extra_labels:
                    labels = list(dict.fromkeys(labels + extra_labels))
                if hasattr(feat_obj, "model_dump"):
                    l0_payload = feat_obj.model_dump(exclude_none=True)
                else:  # pragma: no cover - fallback for BaseModel-like
                    l0_payload = feat_obj.dict(exclude_none=True)  # type: ignore[call-arg]
                l0_payload = {
                    k: v
                    for k, v in l0_payload.items()
                    if v not in (None, [], {}, "")
                }
            else:
                l0_payload = {}
        else:
            l0_payload = {}

        entities: dict[str, Any]
        if isinstance(entities_raw, Mapping):
            entities = {
                k: v
                for k, v in entities_raw.items()
                if v is not None
            }
        else:
            entities = {}
        if l0_payload:
            entities.setdefault("l0", {}).update(l0_payload)

        segment_entries.append(
            {
                "id": seg_id_int if seg_id_int is not None else seg_id,
                "range": {"start": start, "end": end},
                "labels": labels,
                "entities": entities,
                "tokens": {"len": len(seg_text)},
            }
        )

    return {
        "doc": doc_payload,
        "segments": segment_entries,
    }


def build_features(
    doc_norm: ParsedDocument,
    segments: Iterable[Mapping[str, Any]],
    hints: Any,
    l0_features: "LxDocFeatures | None" = None,
) -> TFeatures:
    payload = serialize_features(doc_norm, segments, l0_features)

    if isinstance(hints, str):
        hints_list: list[Any] = [hints]
    elif hints is None:
        hints_list = []
    else:
        try:
            hints_list = list(hints)
        except TypeError:
            hints_list = [hints]

    doc_payload = payload.setdefault("doc", {})
    doc_payload["hints"] = hints_list
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
