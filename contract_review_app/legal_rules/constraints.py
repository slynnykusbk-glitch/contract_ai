"""Utilities for building the ParamGraph and evaluating legal constraints."""

from __future__ import annotations

from decimal import Decimal
import re
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from contract_review_app.analysis.extract_summary import (
    _extract_cure_days,
    _extract_cross_refs,
    _extract_duration_from_text,
    _extract_notice_days,
    _extract_payment_term_days,
    _detect_numbering_gaps,
    _detect_order_of_precedence,
    _detect_undefined_terms,
)
from contract_review_app.core.lx_types import (
    Duration,
    LxDocFeatures,
    Money,
    ParamGraph,
    SourceRef,
)
from contract_review_app.legal_rules.cross_checks import _extract_survival_items

__all__ = ["build_param_graph"]


_ANNEX_RE = re.compile(r"\b(?P<prefix>annex|schedule)\s+(?P<label>[A-Z0-9]+)\b", re.IGNORECASE)
_LAW_PATTERN = re.compile(r"governed\s+by\s+the\s+law", re.IGNORECASE)
_JUR_PATTERN = re.compile(r"jurisdiction", re.IGNORECASE)
_CAP_PATTERN = re.compile(r"liability|cap", re.IGNORECASE)
_CURRENCY_PATTERN = re.compile(r"[$€£]|\bUSD\b|\bEUR\b|\bGBP\b", re.IGNORECASE)
_SURVIVE_PATTERN = re.compile(r"\bsurviv", re.IGNORECASE)
_NOTICE_PATTERN = re.compile(r"notice", re.IGNORECASE)
_CURE_PATTERN = re.compile(r"\b(cure|remedy)\b", re.IGNORECASE)
_PAYMENT_PATTERN = re.compile(r"\b(payment|invoice|fee|remit)\b", re.IGNORECASE)
_GRACE_PATTERN = re.compile(r"grace\s+period", re.IGNORECASE)
_CROSS_PATTERN = re.compile(r"\b(?:clause|section)\s+\d", re.IGNORECASE)


def _iter_segments(segments: Iterable[Any]) -> Iterable[Any]:
    for seg in segments or []:  # type: ignore[truthy-bool]
        yield seg


def _seg_attr(seg: Any, key: str, default: Any = None) -> Any:
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def _combined_text(seg: Any) -> str:
    text = str(_seg_attr(seg, "text", "") or "")
    heading = _seg_attr(seg, "heading")
    if heading:
        return f"{heading}\n{text}" if text else str(heading)
    return text


def _clause_id(seg: Any) -> str:
    number = _seg_attr(seg, "number")
    if isinstance(number, str) and number:
        return number
    seg_id = _seg_attr(seg, "id")
    return str(seg_id) if seg_id is not None else "?"


def _seg_span(seg: Any) -> Optional[Tuple[int, int]]:
    start = _seg_attr(seg, "start")
    end = _seg_attr(seg, "end")
    if isinstance(start, int) and isinstance(end, int):
        return (start, end)
    return None


def _make_source(seg: Any, note: Optional[str] = None) -> SourceRef:
    return SourceRef(clause_id=_clause_id(seg), span=_seg_span(seg), note=note)


def _extract_grace_period(segments: Sequence[Any]) -> Optional[Duration]:
    for seg in segments:
        combined = _combined_text(seg)
        if combined and _GRACE_PATTERN.search(combined):
            lower = combined.lower()
            idx = lower.find("grace period")
            snippet = combined[idx:] if idx >= 0 else combined
            duration = _extract_duration_from_text(snippet)
            if duration:
                return duration
    return None


def _extract_contract_term(l0: Optional[LxDocFeatures]) -> Optional[Duration]:
    if not l0:
        return None
    for seg_id, features in (l0.by_segment or {}).items():
        labels = getattr(features, "labels", [])
        durations = getattr(features, "durations", {})
        if "Term" not in labels:
            continue
        days = durations.get("days")
        if isinstance(days, int) and days > 0:
            return Duration(days=days, kind="calendar")
    return None


def _normalize_currency(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned in Money._symbol_map:
        return Money._symbol_map[cleaned]
    cleaned = cleaned.upper()
    if len(cleaned) == 3:
        return cleaned
    return None


def _annex_refs(full_text: str) -> List[str]:
    refs = set()
    for match in _ANNEX_RE.finditer(full_text or ""):
        prefix = match.group("prefix") or "annex"
        label = match.group("label") or ""
        formatted = f"{prefix.title()} {label.upper()}" if label.isalpha() else f"{prefix.title()} {label}"
        refs.add(formatted)
    return sorted(refs)


def _first_segment_matching(segments: Sequence[Any], pattern: re.Pattern[str]) -> Optional[Any]:
    for seg in segments:
        combined = _combined_text(seg)
        if combined and pattern.search(combined):
            return seg
    return None


def _full_text_from_segments(segments: Sequence[Any]) -> str:
    parts: List[str] = []
    for seg in segments:
        combined = _combined_text(seg)
        if combined:
            parts.append(combined)
    return "\n".join(parts)


def _collect_survival_items(segments: Sequence[Any]) -> set[str]:
    items: set[str] = set()
    for seg in segments:
        combined = _combined_text(seg)
        if combined and _SURVIVE_PATTERN.search(combined):
            items.update(_extract_survival_items(combined))
    return items


def build_param_graph(
    snapshot: Any,
    segments: Sequence[Any],
    l0_features: Optional[LxDocFeatures],
) -> ParamGraph:
    segments_list = list(_iter_segments(segments))
    full_text = _full_text_from_segments(segments_list)
    parsed = SimpleNamespace(normalized_text=full_text, segments=segments_list)

    payment_term = _extract_payment_term_days(parsed, segments_list)
    notice_period = _extract_notice_days(parsed, segments_list)
    cure_period = _extract_cure_days(parsed, segments_list)
    cross_refs = _extract_cross_refs(parsed, segments_list)
    order_of_precedence = _detect_order_of_precedence(parsed, segments_list)
    undefined_terms = _detect_undefined_terms(parsed, segments_list)
    numbering_gaps = _detect_numbering_gaps(parsed, segments_list)
    grace_period = _extract_grace_period(segments_list)
    contract_term = _extract_contract_term(l0_features)
    survival_items = _collect_survival_items(segments_list)
    annex_refs = _annex_refs(full_text)

    parties = []
    try:
        for party in getattr(snapshot, "parties", []) or []:
            if hasattr(party, "model_dump"):
                parties.append(party.model_dump(exclude_none=True))
            elif isinstance(party, dict):
                parties.append({k: v for k, v in party.items() if v is not None})
    except Exception:
        parties = []

    signatures = []
    for sig in getattr(snapshot, "signatures", []) or []:
        if isinstance(sig, dict):
            signatures.append(sig)
        else:
            signatures.append({"raw": str(sig)})

    law = getattr(snapshot, "governing_law", None)
    juris = getattr(snapshot, "jurisdiction", None)

    cap = None
    liability = getattr(snapshot, "liability", None)
    if liability and getattr(liability, "has_cap", False):
        cap_value = getattr(liability, "cap_value", None)
        cap_currency = getattr(liability, "cap_currency", None)
        if cap_value is not None and cap_currency:
            try:
                amount = Decimal(str(cap_value))
                currency = _normalize_currency(cap_currency)
                if currency:
                    cap = Money(amount=amount, currency=currency)
            except Exception:
                cap = None

    contract_currency = _normalize_currency(getattr(snapshot, "currency", None))

    pg = ParamGraph(
        payment_term=payment_term,
        contract_term=contract_term,
        grace_period=grace_period,
        governing_law=law,
        jurisdiction=juris,
        cap=cap,
        contract_currency=contract_currency,
        notice_period=notice_period,
        cure_period=cure_period,
        survival_items=survival_items,
        cross_refs=cross_refs,
        parties=parties,
        signatures=signatures,
        annex_refs=annex_refs,
        order_of_precedence=order_of_precedence,
        undefined_terms=undefined_terms,
        numbering_gaps=numbering_gaps,
    )

    sources: Dict[str, SourceRef] = {}

    seg_payment = _first_segment_matching(segments_list, _PAYMENT_PATTERN)
    if payment_term and seg_payment:
        sources["payment_term"] = _make_source(seg_payment)

    seg_notice = _first_segment_matching(segments_list, _NOTICE_PATTERN)
    if notice_period and seg_notice:
        sources["notice_period"] = _make_source(seg_notice)

    seg_cure = _first_segment_matching(segments_list, _CURE_PATTERN)
    if cure_period and seg_cure:
        sources["cure_period"] = _make_source(seg_cure)

    seg_grace = _first_segment_matching(segments_list, _GRACE_PATTERN)
    if grace_period and seg_grace:
        sources["grace_period"] = _make_source(seg_grace)

    seg_law = _first_segment_matching(segments_list, _LAW_PATTERN)
    if law and seg_law:
        sources["governing_law"] = _make_source(seg_law)

    seg_jur = _first_segment_matching(segments_list, _JUR_PATTERN)
    if juris and seg_jur:
        sources["jurisdiction"] = _make_source(seg_jur)

    seg_cap = _first_segment_matching(segments_list, _CAP_PATTERN)
    if cap and seg_cap:
        sources["cap"] = _make_source(seg_cap)

    seg_currency = _first_segment_matching(segments_list, _CURRENCY_PATTERN)
    if contract_currency and seg_currency:
        sources["contract_currency"] = _make_source(seg_currency)

    seg_survival = _first_segment_matching(segments_list, _SURVIVE_PATTERN)
    if survival_items and seg_survival:
        sources["survival_items"] = _make_source(seg_survival)

    seg_cross = _first_segment_matching(segments_list, _CROSS_PATTERN)
    if cross_refs and seg_cross:
        sources["cross_refs"] = _make_source(seg_cross, note=f"{len(cross_refs)} cross-ref(s)")

    seg_annex = _first_segment_matching(segments_list, _ANNEX_RE)
    if annex_refs and seg_annex:
        sources["annex_refs"] = _make_source(seg_annex)

    if undefined_terms:
        term = undefined_terms[0]
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and term in combined:
                sources["undefined_terms"] = _make_source(seg, note=term)
                break

    if numbering_gaps:
        seg_numbering = None
        for seg in segments_list:
            if _seg_attr(seg, "number"):
                seg_numbering = seg
                break
        if seg_numbering:
            sources["numbering_gaps"] = _make_source(seg_numbering, note=", ".join(map(str, numbering_gaps)))

    if parties:
        seg_parties = None
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and "between" in combined.lower():
                seg_parties = seg
                break
        if seg_parties:
            sources["parties"] = _make_source(seg_parties)

    if signatures:
        seg_sign = None
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and "signed" in combined.lower():
                seg_sign = seg
                break
        if seg_sign:
            sources["signatures"] = _make_source(seg_sign)

    pg.sources = sources
    return pg
