from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from contract_review_app.intake.parser import ParsedDocument

from .types_trace import TConstraints, TDispatch, TFeatures, TProposals

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


def build_features(doc_norm: ParsedDocument, segments: Iterable[Mapping[str, Any]], hints: Any) -> TFeatures:
    norm_text = getattr(doc_norm, "normalized_text", "") or ""
    doc_hash = getattr(doc_norm, "checksum", None)
    if doc_hash is None:
        doc_hash = getattr(doc_norm, "checksum_sha256", None)

    if isinstance(hints, str):
        hints_list: list[Any] = [hints]
    elif hints is None:
        hints_list = []
    else:
        try:
            hints_list = list(hints)
        except TypeError:
            hints_list = [hints]

    doc_payload: dict[str, Any] = {
        "language": _resolve_language(doc_norm),
        "length": len(norm_text),
        "hints": hints_list,
    }
    if doc_hash:
        doc_payload["hash"] = doc_hash

    segment_entries = []
    for seg in segments or []:
        seg_id = seg.get("id") if isinstance(seg, Mapping) else None
        start = int(seg.get("start", 0)) if isinstance(seg, Mapping) else 0
        end = int(seg.get("end", 0)) if isinstance(seg, Mapping) else 0
        clause_type = None
        labels_raw = None
        entities = {}
        text = ""
        if isinstance(seg, Mapping):
            clause_type = seg.get("clause_type")
            labels_raw = seg.get("labels")
            entities = seg.get("entities") or {}
            text = seg.get("text") or ""

        labels = _coerce_labels(clause_type)
        if not labels:
            labels = _coerce_labels(labels_raw)

        segment_entries.append(
            {
                "id": seg_id,
                "range": {"start": start, "end": end},
                "labels": labels,
                "entities": entities if isinstance(entities, Mapping) else {},
                "tokens": {"len": len(text)},
            }
        )

    return {
        "doc": doc_payload,
        "segments": segment_entries,
    }

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


def build_constraints(*args: Any, **kwargs: Any) -> TConstraints:
    return {}


def build_proposals(*args: Any, **kwargs: Any) -> TProposals:
    return {}
