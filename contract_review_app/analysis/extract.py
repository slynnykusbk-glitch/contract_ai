import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_iso(date_str: str) -> str:
    """Best effort normalisation of date strings to ISO format."""
    if not date_str:
        return ""
    cleaned = re.sub(r"(st|nd|rd|th)", "", date_str, flags=re.IGNORECASE).strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return cleaned


# ---------------------------------------------------------------------------
# Contract classification
# ---------------------------------------------------------------------------

_CONTRACT_PATTERNS = [
    (
        re.compile(r"\b(?:non-disclosure|confidentiality) agreement\b|\bNDA\b", re.I),
        "NDA",
        10,
    ),
    (
        re.compile(r"\bmaster\s+(?:services|supply)\s+agreement\b", re.I),
        "Master Services Agreement",
        9,
    ),
    (re.compile(r"\bstatement of work\b|\bSOW\b", re.I), "Statement of Work", 8),
    (re.compile(r"\blicen[cs]e\b", re.I), "License", 7),
    (re.compile(r"\bconsultancy\b", re.I), "Consultancy", 6),
    (re.compile(r"\b(?:purchase|sale) of goods\b", re.I), "Purchase/Sale of Goods", 5),
    (re.compile(r"\bsubcontract\b", re.I), "Subcontract", 4),
    (re.compile(r"\bframework agreement\b", re.I), "Framework Agreement", 3),
    (
        re.compile(r"\bdata processing agreement\b", re.I),
        "Data Processing Agreement",
        2,
    ),
    (re.compile(r"\bservice level agreement\b", re.I), "Service Level Agreement", 1),
]


def classify_contract(text: str) -> Dict[str, Any]:
    """Classify contract type using simple keyword heuristics."""
    best_type = "unknown"
    best_weight = 0
    hints: List[str] = []
    for pattern, ctype, weight in _CONTRACT_PATTERNS:
        m = pattern.search(text or "")
        if m:
            hints.append(m.group(0))
            if weight > best_weight:
                best_type = ctype
                best_weight = weight
    confidence = best_weight / 10 if best_weight else 0.0
    return {"type": best_type, "confidence": round(confidence, 2), "hints": hints}


# ---------------------------------------------------------------------------
# Party extraction
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(
    r"([A-Z][A-Za-z0-9&., ']+?(?:Ltd|Limited|LLP|PLC|Inc|LLC|GmbH|S\.A\.|SAS))",
    re.I,
)
_COMP_NO_RE = re.compile(r"company number\s*([A-Za-z0-9]+)", re.I)
_ADDR_RE = re.compile(r"registered office at\s+([^,.;\n]+)", re.I)


def _parse_party(segment: str) -> Dict[str, Optional[str]]:
    name_match = _NAME_RE.search(segment)
    name = name_match.group(1).strip() if name_match else segment.strip().split(",")[0]
    comp_match = _COMP_NO_RE.search(segment)
    addr_match = _ADDR_RE.search(segment)
    return {
        "name": name.strip(),
        "company_number": comp_match.group(1) if comp_match else None,
        "country": None,
        "address": addr_match.group(1).strip() if addr_match else None,
    }


_BETWEEN_RE = re.compile(r"between\s+(.*?)\s+and\s+(.*?)(?:\n|\.|$)", re.I | re.S)


def extract_parties(text: str) -> List[Dict[str, Optional[str]]]:
    parties: List[Dict[str, Optional[str]]] = []
    m = _BETWEEN_RE.search(text or "")
    if m:
        part_a = _parse_party(m.group(1))
        part_b = _parse_party(m.group(2))
        parties.extend([part_a, part_b])
    return [p for p in parties if p.get("name")]


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

_DATED_RE = re.compile(r"dated\s+(?:the\s+)?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_EFFECTIVE_RE = re.compile(r"effective date[:\s]*?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_COMMENCE_RE = re.compile(r"commencement date[:\s]*?(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_SIGN_RE = re.compile(r"Signed[^\n]*?on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)


def extract_dates(text: str) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "dated": None,
        "effective": None,
        "commencement": None,
        "signatures": [],
    }
    if m := _DATED_RE.search(text or ""):
        res["dated"] = _to_iso(m.group(1))
    if m := _EFFECTIVE_RE.search(text or ""):
        res["effective"] = _to_iso(m.group(1))
    if m := _COMMENCE_RE.search(text or ""):
        res["commencement"] = _to_iso(m.group(1))
    for sm in _SIGN_RE.finditer(text or ""):
        res["signatures"].append({"party": None, "date": _to_iso(sm.group(1))})
    return res


# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(r"(\d+)\s+(day|month|year)s?", re.I)
_AUTO_RENEW_RE = re.compile(r"unless either party gives\s+(\d+)\s+days'? notice", re.I)
_COMMENCE_ON_RE = re.compile(r"commence[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)
_END_ON_RE = re.compile(r"terminate[s]? on\s+(\d{1,2}\s+\w+\s+20\d{2})", re.I)


def extract_term(text: str) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "mode": "unknown",
        "start": None,
        "end": None,
        "renew_notice_days": None,
    }
    if m := _COMMENCE_ON_RE.search(text or ""):
        res["start"] = _to_iso(m.group(1))
    if m := _END_ON_RE.search(text or ""):
        res["end"] = _to_iso(m.group(1))
    if m := _AUTO_RENEW_RE.search(text or ""):
        res["mode"] = "auto_renew"
        res["renew_notice_days"] = int(m.group(1))
    elif _DURATION_RE.search(text or ""):
        res["mode"] = "fixed"
    return res


# ---------------------------------------------------------------------------
# Law & jurisdiction
# ---------------------------------------------------------------------------

_LAW_RE = re.compile(r"laws? of ([A-Za-z\s]+?)(?:\.|,|\n)", re.I)
_JURIS_RE = re.compile(r"courts? of ([A-Za-z\s]+?)(?:\.|,|\n)", re.I)
_EXCLUSIVE_RE = re.compile(r"exclusive jurisdiction", re.I)


def extract_law_jurisdiction(text: str) -> Dict[str, Any]:
    law = None
    juris = None
    if m := _LAW_RE.search(text or ""):
        law = m.group(1).strip()
    if m := _JURIS_RE.search(text or ""):
        juris = m.group(1).strip()
    exclusive = bool(_EXCLUSIVE_RE.search(text or "")) if juris else None
    return {"law": law, "jurisdiction": juris, "exclusive": exclusive}


# ---------------------------------------------------------------------------
# Liability
# ---------------------------------------------------------------------------

_CAP_RE = re.compile(
    r"liability[^.]{0,200}?(?:shall not exceed|cap on liability|aggregate liability)[^.]{0,200}",
    re.I,
)
_MONEY_RE = re.compile(r"(£|€|\$)\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")
_CARVEOUT_TERMS = [
    "fraud",
    "death or personal injury",
    "confidentiality",
    "IP",
    "intellectual property",
    "data protection",
    "bribery",
    "taxes",
    "insurance",
    "HSE",
]


def extract_liability(text: str) -> Dict[str, Any]:
    has_cap = False
    cap_value: Optional[float] = None
    currency: Optional[str] = None
    m = _CAP_RE.search(text or "")
    if m:
        has_cap = True
        tail = text[m.start() : m.end() + 100]
        money = _MONEY_RE.search(tail)
        if money:
            currency = money.group(1)
            try:
                cap_value = float(money.group(2).replace(",", ""))
            except Exception:
                cap_value = None
    carveouts = []
    lower = (text or "").lower()
    for term in _CARVEOUT_TERMS:
        if term.lower() in lower:
            carveouts.append(term)
    return {
        "has_cap": has_cap,
        "cap_value": cap_value,
        "currency": currency,
        "has_carveouts": bool(carveouts),
        "carveouts": carveouts,
    }


# ---------------------------------------------------------------------------
# Conditions vs warranties
# ---------------------------------------------------------------------------

_COND_RE = re.compile(
    r"(shall be a condition|time is of the essence|condition precedent)", re.I
)
_WARR_RE = re.compile(r"(represents and warrants|warrants that|warranty)", re.I)


def extract_conditions_warranties(text: str) -> Dict[str, Any]:
    conditions = [m.group(1) for m in _COND_RE.finditer(text or "")]
    warranties = [m.group(1) for m in _WARR_RE.finditer(text or "")]
    return {"conditions": conditions, "warranties": warranties}
