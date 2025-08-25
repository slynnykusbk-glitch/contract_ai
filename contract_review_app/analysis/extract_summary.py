from __future__ import annotations

import re
from typing import Any, List, Optional

from .summary_schemas import (
    DocumentSnapshot,
    Party,
    TermInfo,
    LiabilityInfo,
    ConditionsVsWarranties,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Contract type patterns with weights (0-10)
_TYPE_PATTERNS = [
    (re.compile(r"\b(?:non-disclosure|confidentiality) agreement\b|\bNDA\b", re.I), "NDA", 10),
    (re.compile(r"\bdata processing agreement\b|\bDPA\b", re.I), "DPA", 9),
    (re.compile(r"\bmaster services agreement\b|\bMSA\b", re.I), "MSA", 8),
    (re.compile(r"\bsoftware as a service\b|\bSaaS\b", re.I), "SaaS", 7),
    (re.compile(r"\bsupply agreement\b|\bsupply contract\b", re.I), "Supply", 6),
    (re.compile(r"\bservices agreement\b", re.I), "Services", 5),
    (re.compile(r"\blicen[cs]e\b", re.I), "License", 4),
]

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
_AUTO_RENEW_RE = re.compile(r"auto[-\s]?renew|unless either party gives\s+(\d+)\s+days'? notice", re.I)
_COMMENCE_ON_RE = re.compile(r"commence[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_END_ON_RE = re.compile(r"terminate[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_PERIOD_RE = re.compile(r"for a period of\s+(\d+\s+\w+)", re.I)

# Law / jurisdiction
_LAW_RE = re.compile(r"governed by the laws? of ([^.,\n]+?)(?=\s+and\s+parties|\.|,|\n)", re.I)
_JURIS_RE = re.compile(r"jurisdiction of the courts? of ([A-Za-z\s]+?)(?:\.|,|\n)", re.I)
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


# ---------------------------------------------------------------------------


def _classify(text: str, hints: List[str]) -> tuple[str, float]:
    best_type = "unknown"
    best_weight = 0
    for pat, typ, weight in _TYPE_PATTERNS:
        m = pat.search(text)
        if m:
            hints.append(m.group(0))
            if weight > best_weight:
                best_type, best_weight = typ, weight
    confidence = best_weight / 10 if best_weight else 0.0
    return best_type, round(confidence, 2)


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


def _extract_law_juris(text: str, hints: List[str]) -> tuple[Optional[str], Optional[str], Optional[bool]]:
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
    return LiabilityInfo(has_cap=has_cap, cap_value=cap_value, cap_currency=cap_currency)


def _extract_carveouts(text: str, hints: List[str]) -> dict:
    items = _CARVEOUT_SENT_RE.findall(text)
    for it in items:
        hints.append(it)
    return {"has_carveouts": bool(items), "carveouts": items}


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

    doc_type, confidence = _classify(text, hints)
    parties = _extract_parties(text, hints)
    dates = _extract_dates(text, hints)
    term = _extract_term(text, hints)
    law, juris, exclusivity = _extract_law_juris(text, hints)
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
    return snapshot
