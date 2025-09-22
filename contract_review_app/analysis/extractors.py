"""Utility extractors for structured contract entities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Tuple

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_CURRENCY_KEYWORDS = {
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "sterling": "GBP",
    "usd": "USD",
    "us$": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
}

_CURRENCY_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}

_AMOUNT_PATTERN = re.compile(
    r"""
    (?P<prefix>(?:gbp|eur|usd|us\$))?      # currency words before the number
    \s*                                     # optional whitespace
    (?P<symbol>[£€$])?                      # currency symbol
    \s*                                     # optional whitespace
    (?P<number>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)  # numeric part
    (?:\s*(?P<scale>thousand|million|billion|k|m|mm|bn))?        # scale words
    (?:\s*(?P<suffix>(?:gbp|eur|usd|us\$|pounds?|dollars?|sterling|euros?))
        (?=[\s.,;:!?]|$))?                 # currency words after the number
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PERCENT_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*(?:%|percent|per\s*cent)",
    re.IGNORECASE,
)

_BOE_PATTERN = re.compile(
    r"\b(?:bank\s+of\s+england|boe)\s+base(?:\s+rate)?\s*(?P<op>[+\-])\s*(?P<number>\d+(?:\.\d+)?)%?",
    re.IGNORECASE,
)

_DURATION_PATTERN = re.compile(
    r"\b(?P<number>\d+)[-\s]*(?P<unit>day|days|week|weeks|month|months|year|years)\b",
    re.IGNORECASE,
)

_ISO_DATE_PATTERN = re.compile(r"\b(?P<iso>\d{4}-\d{2}-\d{2})\b")
_UK_DATE_PATTERN = re.compile(r"\b(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{2,4})\b")
_TEXTUAL_DATE_PATTERN = re.compile(
    r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{2,4})\b",
    re.IGNORECASE,
)

_LAW_PATTERNS = [
    (re.compile(r"\b(?:laws?|law)\s+of\s+(?P<target>[A-Za-z& ,'-]+)", re.IGNORECASE), "target"),
    (re.compile(r"\bgoverned\s+by\s+(?P<target>[A-Za-z& ,'-]+)\s+law\b", re.IGNORECASE), "target"),
    (re.compile(r"\b(?P<target>english|scottish|irish)\s+law\b", re.IGNORECASE), "target"),
]

_JURISDICTION_PATTERNS = [
    (re.compile(r"\b(?:jurisdiction|courts?)\s+of\s+(?P<target>[A-Za-z& ,'-]+)", re.IGNORECASE), "target"),
    (re.compile(r"\bsubmit\s+to\s+the\s+(?P<target>[A-Za-z& ,'-]+)\s+courts\b", re.IGNORECASE), "target"),
    (re.compile(r"\b(?P<target>english|scottish|irish)\s+courts\b", re.IGNORECASE), "target"),
]

_INCOTERM_PATTERN = re.compile(
    r"\b(FOB|CIF|CFR|CPT|CIP|DAP|DPU|DDP|EXW|FCA|FAS)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    value: str


_LAW_CANON = [
    _Rule(re.compile(r"england\s*(?:and|&)?\s*wales", re.IGNORECASE), "england-wales"),
    _Rule(re.compile(r"\bengland\b", re.IGNORECASE), "england-wales"),
    _Rule(re.compile(r"english", re.IGNORECASE), "england-wales"),
    _Rule(re.compile(r"scotland", re.IGNORECASE), "scotland"),
    _Rule(re.compile(r"scottish", re.IGNORECASE), "scotland"),
    _Rule(re.compile(r"northern\s+ireland", re.IGNORECASE), "northern-ireland"),
    _Rule(re.compile(r"republic\s+of\s+ireland", re.IGNORECASE), "ireland"),
    _Rule(re.compile(r"\bireland\b", re.IGNORECASE), "ireland"),
    _Rule(re.compile(r"irish", re.IGNORECASE), "ireland"),
    _Rule(re.compile(r"new\s+york", re.IGNORECASE), "us-ny"),
    _Rule(re.compile(r"delaware", re.IGNORECASE), "us-de"),
    _Rule(re.compile(r"california", re.IGNORECASE), "us-ca"),
    _Rule(re.compile(r"texas", re.IGNORECASE), "us-tx"),
    _Rule(re.compile(r"france", re.IGNORECASE), "france"),
    _Rule(re.compile(r"germany", re.IGNORECASE), "germany"),
    _Rule(re.compile(r"netherlands", re.IGNORECASE), "netherlands"),
    _Rule(re.compile(r"singapore", re.IGNORECASE), "singapore"),
    _Rule(re.compile(r"hong\s*kong", re.IGNORECASE), "hong-kong"),
]


_ROLE_PATTERNS: Dict[str, Dict[re.Pattern[str], str]] = {
    "default": {
        re.compile(r"\bsupplier\b", re.IGNORECASE): "supplier",
        re.compile(r"\bcustomer\b", re.IGNORECASE): "customer",
        re.compile(r"\bclient\b", re.IGNORECASE): "client",
        re.compile(r"\bbuyer\b", re.IGNORECASE): "buyer",
        re.compile(r"\bseller\b", re.IGNORECASE): "seller",
        re.compile(r"\blicensor\b", re.IGNORECASE): "licensor",
        re.compile(r"\blicensee\b", re.IGNORECASE): "licensee",
    },
    "tenancy": {
        re.compile(r"\blandlord\b", re.IGNORECASE): "landlord",
        re.compile(r"\blessor\b", re.IGNORECASE): "landlord",
        re.compile(r"\btenant\b", re.IGNORECASE): "tenant",
        re.compile(r"\blessee\b", re.IGNORECASE): "tenant",
    },
    "joa": {
        re.compile(r"\bnon-operator\b", re.IGNORECASE): "non-operator",
        re.compile(r"\bnon\s*operating\s*partner\b", re.IGNORECASE): "non-operator",
        re.compile(r"\boperator\b", re.IGNORECASE): "operator",
        re.compile(r"\bco-venturer\b", re.IGNORECASE): "co-venturer",
    },
}


def _normalise_currency(
    prefix: Optional[str],
    symbol: Optional[str],
    suffix: Optional[str],
    text: str,
) -> Optional[str]:
    for candidate in (prefix, suffix):
        if candidate:
            candidate_norm = candidate.lower()
            if candidate_norm in _CURRENCY_KEYWORDS:
                return _CURRENCY_KEYWORDS[candidate_norm]
    if symbol and symbol in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[symbol]
    # attempt to infer from surrounding text
    lowered = text.lower()
    for keyword, value in _CURRENCY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return value
    return None


def _parse_decimal(number: str, scale: Optional[str]) -> Optional[Decimal]:
    try:
        amount = Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None

    if not scale:
        return amount

    scale_norm = scale.lower()
    multipliers = {
        "thousand": Decimal("1000"),
        "k": Decimal("1000"),
        "million": Decimal("1000000"),
        "m": Decimal("1000000"),
        "mm": Decimal("1000000"),
        "billion": Decimal("1000000000"),
        "bn": Decimal("1000000000"),
    }
    multiplier = multipliers.get(scale_norm)
    if multiplier is None:
        return amount
    return amount * multiplier


def _decimal_to_number(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    if integral == value:
        return int(integral)
    return float(value)


def _iso_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _clean_target(value: str) -> Tuple[str, int]:
    leading_ws = len(value) - len(value.lstrip())
    stripped = value.strip()
    no_punct = re.sub(r"[.,;]+$", "", stripped)
    return no_punct, leading_ws


def _canon_value(raw: str) -> Optional[Tuple[str, Tuple[int, int]]]:
    clean = raw.lower()
    for rule in _LAW_CANON:
        match = rule.pattern.search(clean)
        if match:
            return rule.value, match.span()
    return None


def _add_match(results: List[Dict[str, object]], start: int, end: int, value: object, kind: str) -> None:
    results.append({"start": start, "end": end, "value": value, "kind": kind})


def extract_amounts(text: str) -> List[Dict[str, object]]:
    """Extract monetary amounts with offsets and normalized values."""

    results: List[Dict[str, object]] = []
    for match in _AMOUNT_PATTERN.finditer(text):
        currency = _normalise_currency(
            match.group("prefix"),
            match.group("symbol"),
            match.group("suffix"),
            match.group(0),
        )
        if not currency:
            continue

        amount = _parse_decimal(match.group("number"), match.group("scale"))
        if amount is None:
            continue

        value = {"currency": currency, "amount": _decimal_to_number(amount)}
        _add_match(results, match.start(), match.end(), value, "amount")
    return results


def extract_percentages(text: str) -> List[Dict[str, object]]:
    """Extract percentage values and Bank of England base spreads."""

    results: List[Dict[str, object]] = []

    boe_spans = []
    for match in _BOE_PATTERN.finditer(text):
        number = float(match.group("number"))
        if match.group("op") == "-":
            number *= -1
        value = {"base": "boe_base", "adjustment": number}
        span = (match.start(), match.end())
        boe_spans.append(span)
        _add_match(results, span[0], span[1], value, "percentage_spread")

    for match in _PERCENT_PATTERN.finditer(text):
        number = float(match.group("number"))
        span = (match.start(), match.end())
        if any(span[0] >= start and span[1] <= end for start, end in boe_spans):
            continue
        value = {"percentage": number}
        _add_match(results, span[0], span[1], value, "percentage")

    results.sort(key=lambda item: item["start"])
    return results


def extract_durations(text: str) -> List[Dict[str, object]]:
    """Extract durations and normalise to ISO-8601 strings."""

    unit_to_code = {
        "day": "D",
        "days": "D",
        "week": "W",
        "weeks": "W",
        "month": "M",
        "months": "M",
        "year": "Y",
        "years": "Y",
    }

    results: List[Dict[str, object]] = []
    for match in _DURATION_PATTERN.finditer(text):
        number = match.group("number")
        unit = match.group("unit").lower()
        code = unit_to_code.get(unit)
        if not code:
            continue
        iso_duration = f"P{int(number)}{code}"
        _add_match(results, match.start(), match.end(), {"duration": iso_duration}, "duration")
    return results


def extract_dates(text: str) -> List[Dict[str, object]]:
    """Extract calendar dates and normalise to ISO format."""

    results: List[Dict[str, object]] = []
    seen_spans = set()

    for match in _ISO_DATE_PATTERN.finditer(text):
        value = match.group("iso")
        span = (match.start(), match.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        _add_match(results, span[0], span[1], {"date": value}, "date")

    for match in _UK_DATE_PATTERN.finditer(text):
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        iso = _iso_date(year, month, day)
        if not iso:
            continue
        span = (match.start(), match.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        _add_match(results, span[0], span[1], {"date": iso}, "date")

    for match in _TEXTUAL_DATE_PATTERN.finditer(text):
        day = int(match.group("day"))
        month_name = match.group("month").lower()
        month = _MONTHS.get(month_name)
        if not month:
            continue
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        iso = _iso_date(year, month, day)
        if not iso:
            continue
        span = (match.start(), match.end())
        if span in seen_spans:
            continue
        seen_spans.add(span)
        _add_match(results, span[0], span[1], {"date": iso}, "date")

    results.sort(key=lambda item: item["start"])
    return results


def _extract_norm(
    patterns: Iterable[Tuple[re.Pattern[str], str]], text: str, kind: str
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    seen_spans = set()
    for pattern, group_name in patterns:
        for match in pattern.finditer(text):
            cleaned, lead_trim = _clean_target(match.group(group_name))
            canon = _canon_value(cleaned)
            if not canon:
                continue
            canon_value, (canon_start, canon_end) = canon
            base_start = match.start(group_name) + lead_trim
            span = (base_start + canon_start, base_start + canon_end)
            if span in seen_spans:
                continue
            seen_spans.add(span)
            _add_match(results, span[0], span[1], {"code": canon_value}, kind)
    results.sort(key=lambda item: item["start"])
    return results


def extract_law(text: str) -> List[Dict[str, object]]:
    """Extract governing law references."""

    return _extract_norm(_LAW_PATTERNS, text, "law")


def extract_jurisdiction(text: str) -> List[Dict[str, object]]:
    """Extract jurisdiction references."""

    return _extract_norm(_JURISDICTION_PATTERNS, text, "jurisdiction")


def extract_incoterms(text: str) -> List[Dict[str, object]]:
    """Extract Incoterms codes from text."""

    results: List[Dict[str, object]] = []
    for match in _INCOTERM_PATTERN.finditer(text):
        code = match.group(0).upper()
        _add_match(results, match.start(), match.end(), {"code": code}, "incoterm")
    return results


def extract_roles(text: str, domain: Optional[str] = None) -> List[Dict[str, object]]:
    """Extract party roles, optionally domain specific."""

    domain_key = (domain or "").lower()
    patterns: Dict[re.Pattern[str], str] = {}
    if domain_key and domain_key in _ROLE_PATTERNS:
        patterns.update(_ROLE_PATTERNS[domain_key])
    patterns.update(_ROLE_PATTERNS["default"])

    results: List[Dict[str, object]] = []
    spans: List[Tuple[int, int]] = []
    for pattern, value in patterns.items():
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(not (span[1] <= existing[0] or span[0] >= existing[1]) for existing in spans):
                continue
            spans.append(span)
            _add_match(results, match.start(), match.end(), {"role": value}, "role")
    results.sort(key=lambda item: item["start"])
    return results

