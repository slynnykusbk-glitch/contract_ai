from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from .summary_schemas import (
    DocumentSnapshot,
    Party,
    TermInfo,
    LiabilityInfo,
    ConditionsVsWarranties,
)

from contract_review_app.engine.doc_type import guess_doc_type, slug_to_display
from contract_review_app.core.lx_types import Duration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROLE_RE = re.compile(
    r"\((?:the\s+)?(Disclosing Party|Receiving Party|Seller|Buyer|Licensor|Licensee)\)",
    re.I,
)
_BETWEEN_RE = re.compile(r"between\s+(.*?)\s+and\s+(.*?)(?:\n|\.|$)", re.I | re.S)

# Date patterns
_DATED_RE = re.compile(r"dated\s+(?:the\s+)?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_EFFECTIVE_RE = re.compile(r"effective date[:\s]*?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_COMMENCE_RE = re.compile(r"commencement date[:\s]*?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_SIGN_RE = re.compile(r"SIGNED by[^\n]*", re.I)

# Term patterns
_AUTO_RENEW_RE = re.compile(
    r"auto[-\s]?renew|unless either party gives\s+(\d+)\s+days'? notice", re.I
)
_COMMENCE_ON_RE = re.compile(r"commence[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_END_ON_RE = re.compile(r"terminate[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_PERIOD_RE = re.compile(r"for a period of\s+(\d+\s+\w+)", re.I)

# Law / jurisdiction
_LAW_RE = re.compile(
    r"governed by the laws? of ([^.,\n]+?)(?=\s+and\s+parties|\.|,|\n)", re.I
)
_JURIS_RE = re.compile(
    r"jurisdiction of the courts? of ([A-Za-z\s]+?)(?:\.|,|\n)", re.I
)
_EXCLUSIVE_RE = re.compile(r"\bexclusive jurisdiction\b", re.I)
_NONEXCLUSIVE_RE = re.compile(r"\bnon-exclusive\b", re.I)

# Liability
_CAP_RE = re.compile(
    r"liability[^.]{0,200}?(?:shall not exceed|aggregate liability|cap on liability)[^.]{0,200}",
    re.I,
)
_MONEY_RE = re.compile(r"(£|€|\$)\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")
_CURRENCY_FIRST_RE = re.compile(r"(£|€|\$|USD|EUR|GBP)")

# Carve-outs (simple heuristic)
_CARVEOUT_SENT_RE = re.compile(r"shall not include[^.]+|carve-?outs?:[^.]+", re.I)

# Conditions vs warranties
_COND_RE = re.compile(r"[^.]*condition[^.]*", re.I)
_WARR_RE = re.compile(r"[^.]*warrant[^.]*", re.I)


_CURRENCY_MAP = {"£": "GBP", "$": "USD", "€": "EUR"}


_SUBJECT_SECTIONS = ("purpose", "scope", "services", "background", "recitals")
_SUBJECT_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = tuple(
    (sec, re.compile(rf"^\s*{sec}\b[\s:]*\n(.{{0,400}})", re.I | re.M))
    for sec in _SUBJECT_SECTIONS
)


def _iter_segments(
    segments: Iterable[Any],
) -> Iterable[
    Tuple[int, str, Optional[str], Optional[int], Optional[int], Optional[str]]
]:
    """Yield normalized segment information from dicts/objects."""

    for seg in segments or []:  # type: ignore[truthy-bool]
        if isinstance(seg, dict):
            seg_id = int(seg.get("id", 0) or 0)
            text = str(seg.get("text", "") or "")
            heading = seg.get("heading") or None
            start = seg.get("start") if isinstance(seg.get("start"), int) else None
            end = seg.get("end") if isinstance(seg.get("end"), int) else None
            number = seg.get("number") or None
        else:
            seg_id = int(getattr(seg, "id", 0) or 0)
            text = str(getattr(seg, "text", "") or "")
            heading = getattr(seg, "heading", None)
            start = getattr(seg, "start", None)
            end = getattr(seg, "end", None)
            number = getattr(seg, "number", None)
        yield seg_id, text, heading, start, end, (
            number if isinstance(number, str) else None
        )


_DURATION_IN_DAYS_RE = re.compile(
    r"(?P<num>\d{1,4})(?:\s*\)\s*)?(?P<kind>\s*(?:business|calendar))?\s*days?",
    re.IGNORECASE,
)
_NET_TERM_RE = re.compile(r"\bnet\s+(?P<num>\d{1,4})\b", re.IGNORECASE)
_NOTICE_KEYWORDS = re.compile(r"notice", re.IGNORECASE)
_CURE_KEYWORDS = re.compile(r"\b(cure|remedy)\b", re.IGNORECASE)
_PAYMENT_KEYWORDS = re.compile(r"\b(payment|invoice|fee|remit)\b", re.IGNORECASE)
_ORDER_OF_PRECEDENCE_RE = re.compile(
    r"order of precedence|precedence of documents|priority of documents",
    re.IGNORECASE,
)
_CLAUSE_REF_RE = re.compile(r"\b(?:clause|section)\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
_TERM_IN_QUOTES_RE = re.compile(r"[\"“”']([A-Z][A-Za-z0-9\s-]{1,50})[\"”']")
_DEFINED_TERM_RE = re.compile(
    r"[\"“”']([A-Z][A-Za-z0-9\s-]{1,50})[\"”']\s+(?:shall\s+mean|means|refers\s+to)",
    re.IGNORECASE,
)


def _combine_heading_text(heading: Optional[str], text: str) -> str:
    heading = heading or ""
    if heading:
        return f"{heading}\n{text}" if text else heading
    return text


def _make_duration(value: int, kind: str) -> Duration:
    kind_norm = "business" if kind.lower().strip() == "business" else "calendar"
    if kind_norm == "business":
        approx = max(1, round(value * 7 / 5))
        return Duration(days=int(approx), kind="business")
    return Duration(days=int(value), kind="calendar")


def _extract_duration_from_text(text: str) -> Optional[Duration]:
    for m in _DURATION_IN_DAYS_RE.finditer(text):
        try:
            value = int(m.group("num"))
        except Exception:
            continue
        kind = m.group("kind") or "calendar"
        return _make_duration(value, kind)
    return None


def _extract_payment_term_days(
    parsed: Any, segments: Sequence[Any]
) -> Optional[Duration]:
    text = getattr(parsed, "normalized_text", "") or ""
    if m := _NET_TERM_RE.search(text):
        try:
            return Duration(days=int(m.group("num")), kind="calendar")
        except Exception:
            pass
    for _, seg_text, heading, _, _, _ in _iter_segments(segments):
        combined = _combine_heading_text(heading, seg_text)
        if not combined or not _PAYMENT_KEYWORDS.search(combined):
            continue
        if duration := _extract_duration_from_text(combined):
            return duration
    return None


def _extract_notice_days(parsed: Any, segments: Sequence[Any]) -> Optional[Duration]:
    for _, seg_text, heading, _, _, _ in _iter_segments(segments):
        combined = _combine_heading_text(heading, seg_text)
        if not combined or not _NOTICE_KEYWORDS.search(combined):
            continue
        if duration := _extract_duration_from_text(combined):
            return duration
    return None


def _extract_cure_days(parsed: Any, segments: Sequence[Any]) -> Optional[Duration]:
    for _, seg_text, heading, _, _, _ in _iter_segments(segments):
        combined = _combine_heading_text(heading, seg_text)
        if not combined or not _CURE_KEYWORDS.search(combined):
            continue
        if duration := _extract_duration_from_text(combined):
            return duration
    return None


def _extract_cross_refs(parsed: Any, segments: Sequence[Any]) -> List[Tuple[str, str]]:
    refs: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    last_number: Optional[str] = None
    for seg_id, seg_text, heading, _, _, number in _iter_segments(segments):
        combined = _combine_heading_text(heading, seg_text)
        if not combined:
            continue
        if number:
            last_number = number
        source = number or last_number or str(seg_id)
        for match in _CLAUSE_REF_RE.finditer(combined):
            target = match.group(1)
            pair = (str(source), target)
            if pair not in seen:
                refs.append(pair)
                seen.add(pair)
    return refs


def _detect_order_of_precedence(parsed: Any, segments: Sequence[Any]) -> bool:
    text = getattr(parsed, "normalized_text", "") or ""
    if _ORDER_OF_PRECEDENCE_RE.search(text):
        return True
    for _, seg_text, heading, _, _, _ in _iter_segments(segments):
        combined = _combine_heading_text(heading, seg_text)
        if combined and _ORDER_OF_PRECEDENCE_RE.search(combined):
            return True
    return False


def _detect_undefined_terms(parsed: Any, segments: Sequence[Any]) -> List[str]:
    text = getattr(parsed, "normalized_text", "") or ""
    all_terms = {m.strip() for m in _TERM_IN_QUOTES_RE.findall(text)}
    defined_terms = {m.strip() for m in _DEFINED_TERM_RE.findall(text)}
    undefined = sorted(term for term in all_terms if term and term not in defined_terms)
    return undefined


def _detect_numbering_gaps(parsed: Any, segments: Sequence[Any]) -> List[int]:
    top_numbers: set[int] = set()
    for _, _, _, _, _, number in _iter_segments(segments):
        if not number:
            continue
        m = re.match(r"(\d+)", number)
        if not m:
            continue
        try:
            top_numbers.add(int(m.group(1)))
        except Exception:
            continue
    if not top_numbers:
        return []
    ordered = sorted(top_numbers)
    start = ordered[0]
    end = ordered[-1]
    gaps = [n for n in range(start, end + 1) if n not in top_numbers]
    return gaps


def _extract_parties(text: str, hints: List[str]) -> List[Party]:
    parties: List[Party] = []
    m = _BETWEEN_RE.search(text)
    if m:
        for seg in [m.group(1), m.group(2)]:
            role = None
            r = _ROLE_RE.search(seg)
            if r:
                role = r.group(1)
                hints.append(r.group(0))
            name = re.sub(r"\(.*?\)", "", seg).strip(' ",.;')
            parties.append(Party(role=role, name=name))
    return [p for p in parties if p.name]


def _extract_dates(text: str, hints: List[str]) -> dict:
    res = {"dated": None, "effective": None, "commencement": None}
    if m := _DATED_RE.search(text):
        res["dated"] = m.group(1)
        hints.append(m.group(0))
    if m := _EFFECTIVE_RE.search(text):
        res["effective"] = m.group(1)
        hints.append(m.group(0))
    if m := _COMMENCE_RE.search(text):
        res["commencement"] = m.group(1)
        hints.append(m.group(0))
    return res


def _extract_signatures(text: str) -> List[str]:
    return _SIGN_RE.findall(text or "")


def _extract_term(text: str, hints: List[str]) -> TermInfo:
    mode = "unknown"
    start = end = notice = None
    if m := _COMMENCE_ON_RE.search(text):
        start = m.group(1)
        hints.append(m.group(0))
    if m := _END_ON_RE.search(text):
        end = m.group(1)
        hints.append(m.group(0))
    if m := _AUTO_RENEW_RE.search(text):
        mode = "auto_renew"
        notice = m.group(1) if m.lastindex else None
        hints.append(m.group(0))
    elif _PERIOD_RE.search(text):
        mode = "fixed"
        hints.append(_PERIOD_RE.search(text).group(0))
    return TermInfo(mode=mode, start=start, end=end, renew_notice=notice)


def _extract_law_juris(
    text: str, hints: List[str]
) -> tuple[Optional[str], Optional[str], Optional[bool]]:
    law = juris = None
    exclusivity: Optional[bool] = None
    if m := _LAW_RE.search(text):
        law = m.group(1).strip()
        hints.append(m.group(0))
    if m := _JURIS_RE.search(text):
        juris = m.group(1).strip()
        hints.append(m.group(0))
        if _EXCLUSIVE_RE.search(text):
            exclusivity = True
            hints.append(_EXCLUSIVE_RE.search(text).group(0))
        elif _NONEXCLUSIVE_RE.search(text):
            exclusivity = False
            hints.append(_NONEXCLUSIVE_RE.search(text).group(0))
    return law, juris, exclusivity


def _extract_liability(text: str, hints: List[str]) -> LiabilityInfo:
    has_cap = False
    cap_value = None
    cap_currency = None
    if m := _CAP_RE.search(text):
        has_cap = True
        hints.append(m.group(0))
        tail = text[m.start() : m.end() + 100]
        if money := _MONEY_RE.search(tail):
            sym = money.group(1)
            val = money.group(2).replace(",", "")
            try:
                cap_value = float(val)
            except Exception:
                cap_value = None
            cap_currency = _CURRENCY_MAP.get(sym, sym)
            hints.append(money.group(0))
    return LiabilityInfo(
        has_cap=has_cap, cap_value=cap_value, cap_currency=cap_currency
    )


def _extract_carveouts(text: str, hints: List[str]) -> dict:
    items = _CARVEOUT_SENT_RE.findall(text)
    if not items:
        lower = text.lower()
        if "fraud" in lower:
            items.append("fraud")
        if "confidential" in lower:
            items.append("confidentiality")
    for it in items:
        hints.append(it)
    return {"has_carveouts": bool(items), "list": items, "carveouts": items}


def _extract_cw(text: str, hints: List[str]) -> ConditionsVsWarranties:
    conds = _COND_RE.findall(text)
    warts = _WARR_RE.findall(text)
    hints.extend(conds + warts)
    return ConditionsVsWarranties(
        has_conditions=bool(conds),
        has_warranties=bool(warts),
        explicit_conditions=conds,
        explicit_warranties=warts,
    )


def _extract_subject(text: str) -> Optional[dict]:
    for sec, pattern in _SUBJECT_PATTERNS:
        m = pattern.search(text)
        if m:
            content = m.group(1).strip()
            sentences = re.split(r"(?<=[.!?])\s+", content)
            raw = " ".join(sentences[:2]).strip()
            return {"title": sec.title(), "raw": raw}
    return None


def _first_currency(text: str) -> Optional[str]:
    m = _CURRENCY_FIRST_RE.search(text)
    if not m:
        return None
    sym = m.group(1)
    return _CURRENCY_MAP.get(sym, sym)


# ---------------------------------------------------------------------------


def extract_document_snapshot(text: str) -> DocumentSnapshot:
    """Extract a document snapshot using simple heuristics (no LLM)."""
    text = text or ""
    hints: List[str] = []

    subject = _extract_subject(text)
    subject_raw = subject.get("raw") if subject else None

    slug, confidence, evidence, score_map, source = guess_doc_type(text, subject_raw)
    doc_type = slug_to_display(slug)
    if confidence < 0.1:
        doc_type = "unknown"
    if doc_type == "License (IP)" and "ip" not in text.lower():
        doc_type = "License"
    doc_type_source = source if doc_type != "unknown" else None
    hints.extend(evidence[:5])
    parties = _extract_parties(text, hints)
    dates = _extract_dates(text, hints)
    term = _extract_term(text, hints)
    law, juris, exclusivity = _extract_law_juris(text, hints)
    if not juris:
        juris = law
    liability = _extract_liability(text, hints)
    carveouts = _extract_carveouts(text, hints)
    cw = _extract_cw(text, hints)
    signatures = _extract_signatures(text)
    currency = _first_currency(text)

    try:
        from contract_review_app.legal_rules import registry as rules_registry  # type: ignore

        rules_count = len(getattr(rules_registry, "rules", []))
    except Exception:
        rules_count = 0

    snapshot = DocumentSnapshot(
        type=doc_type,
        type_confidence=confidence,
        type_source=doc_type_source,
        parties=parties,
        dates=dates,
        term=term,
        governing_law=law,
        jurisdiction=juris,
        signatures=signatures,
        liability=liability,
        exclusivity=exclusivity,
        currency=currency,
        carveouts=carveouts,
        conditions_vs_warranties=cw,
        hints=hints,
        rules_count=rules_count,
    )
    if subject:
        try:
            object.__setattr__(snapshot, "subject", subject)
        except Exception:
            pass
    # Expose top document type candidates for debugging/clients
    try:
        debug_top = [
            {"type": slug_to_display(s), "score": round(v, 3)}
            for s, v in sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[
                :5
            ]
        ]
        if debug_top:
            object.__setattr__(snapshot, "debug", {"doctype_top": debug_top})
    except Exception:
        pass
    return snapshot
