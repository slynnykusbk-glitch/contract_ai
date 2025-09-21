from __future__ import annotations

from typing import Any, Iterable, Mapping

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


def build_dispatch(*args: Any, **kwargs: Any) -> TDispatch:
    return {}


def build_constraints(*args: Any, **kwargs: Any) -> TConstraints:
    return {}


def build_proposals(*args: Any, **kwargs: Any) -> TProposals:
    return {}
