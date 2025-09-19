"""Lightweight feature extraction for LX pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set
import re

from .parser import ParsedDoc
from .extract import (
    _COMP_NO_RE,
    _DURATION_RE,
    _JURIS_RE,
    _LAW_RE,
    _MONEY_RE,
)


@dataclass
class LxSegmentFeatures:
    """Features extracted for a single document segment."""

    segment_id: int
    text: str
    labels: Set[str] = field(default_factory=set)
    durations: Dict[str, List[int]] = field(default_factory=dict)
    amounts: List[Dict[str, Optional[float]]] = field(default_factory=list)
    company_numbers: List[str] = field(default_factory=list)
    governing_law: List[str] = field(default_factory=list)
    jurisdictions: List[str] = field(default_factory=list)

    def add_duration(self, unit: str, value: int) -> None:
        values = self.durations.setdefault(unit, [])
        values.append(value)

    def add_amount(self, currency: str, value: Optional[float]) -> None:
        self.amounts.append({"currency": currency, "value": value})

    def finalize(self) -> None:
        self.durations = _finalize_numeric_map(self.durations)


@dataclass
class LxDocFeatures:
    """Aggregated features for an entire document."""

    segments: Dict[int, LxSegmentFeatures]
    labels: Set[str]
    durations: Dict[str, Iterable[int] | int]
    amounts: List[Dict[str, Optional[float]]]
    company_numbers: List[str]
    governing_law: List[str]
    jurisdictions: List[str]


def _finalize_numeric_map(raw: Dict[str, List[int]]) -> Dict[str, Iterable[int] | int]:
    result: Dict[str, Iterable[int] | int] = {}
    for unit, values in raw.items():
        if not values:
            continue
        unique_sorted = sorted(set(values))
        if len(unique_sorted) == 1:
            result[unit] = unique_sorted[0]
        else:
            result[unit] = unique_sorted
    return result


_LABEL_PATTERNS: Dict[str, re.Pattern[str]] = {
    "Payment": re.compile(r"\b(payment|remuneration|invoice)\b", re.I),
    "Term": re.compile(r"\bterm\b|\bremain in force\b", re.I),
    "Liability": re.compile(r"\bliabilit", re.I),
    "Confidentiality": re.compile(r"\bconfidential", re.I),
    "Indemnity": re.compile(r"\bindemnif", re.I),
    "GoverningLaw": re.compile(r"\bgoverning law\b", re.I),
    "Jurisdiction": re.compile(r"\bjurisdiction\b", re.I),
    "Dispute": re.compile(r"\bdispute\b", re.I),
    "IP": re.compile(r"\bintellectual property\b|\bIP\b", re.I),
    "Notices": re.compile(r"\bnotice(s)?\b", re.I),
    "Taxes": re.compile(r"\btax(es)?\b", re.I),
    "SetOff": re.compile(r"set[-\s]?off", re.I),
    "Interest": re.compile(r"\binterest\b", re.I),
    "Price": re.compile(r"\bprice\b|\bpricing\b", re.I),
    "SLA": re.compile(r"service level agreement|\bSLA\b", re.I),
    "KPI": re.compile(r"key performance indicator|\bKPI\b", re.I),
    "Acceptance": re.compile(r"\bacceptance\b", re.I),
    "Boilerplate": re.compile(r"\bthis agreement\b|\bhereby\b|\bthereof\b", re.I),
}


def _detect_labels(text: str) -> Set[str]:
    labels: Set[str] = set()
    for label, pattern in _LABEL_PATTERNS.items():
        if pattern.search(text):
            labels.add(label)
    return labels


def _normalise_parenthetical_numbers(text: str) -> str:
    return re.sub(r"\((\d+)\)", r" \1 ", text)


def _extract_durations(text: str, segment: LxSegmentFeatures) -> None:
    seen: Set[tuple[str, int]] = set()
    for source in (text, _normalise_parenthetical_numbers(text)):
        for match in _DURATION_RE.finditer(source):
            value = int(match.group(1))
            unit = match.group(2).lower()
            if unit.endswith("s"):
                unit = unit[:-1]
            key = (unit, value)
            if key in seen:
                continue
            seen.add(key)
            segment.add_duration(f"{unit}s" if not unit.endswith("s") else unit, value)


def _extract_amounts(text: str, segment: LxSegmentFeatures) -> None:
    for match in _MONEY_RE.finditer(text):
        currency = match.group(1)
        raw_value = match.group(2)
        try:
            value = float(raw_value.replace(",", ""))
        except Exception:
            value = None
        segment.add_amount(currency, value)


def _extract_company_numbers(text: str) -> List[str]:
    return [m.group(1) for m in _COMP_NO_RE.finditer(text)]


def _extract_law(text: str) -> List[str]:
    if m := _LAW_RE.search(text):
        return [m.group(1).strip()]
    return []


def _extract_jurisdiction(text: str) -> List[str]:
    if m := _JURIS_RE.search(text):
        return [m.group(1).strip()]
    return []


def extract_l0_features(parsed: ParsedDoc) -> LxDocFeatures:
    segments: Dict[int, LxSegmentFeatures] = {}
    aggregate_labels: Set[str] = set()
    aggregate_durations: Dict[str, List[int]] = {}
    aggregate_amounts: List[Dict[str, Optional[float]]] = []
    aggregate_company_numbers: Set[str] = set()
    aggregate_law: List[str] = []
    aggregate_jurisdiction: List[str] = []

    for seg in parsed.segments:
        seg_id = int(seg.get("id", 0))
        text = str(seg.get("text", ""))
        features = LxSegmentFeatures(segment_id=seg_id, text=text)

        features.labels = _detect_labels(text)
        aggregate_labels.update(features.labels)

        _extract_durations(text, features)
        for unit, values in features.durations.items():
            aggregate_durations.setdefault(unit, []).extend(values)

        _extract_amounts(text, features)
        aggregate_amounts.extend(features.amounts)

        company_numbers = _extract_company_numbers(text)
        features.company_numbers.extend(company_numbers)
        aggregate_company_numbers.update(company_numbers)

        laws = _extract_law(text)
        jurisdictions = _extract_jurisdiction(text)
        features.governing_law.extend(laws)
        features.jurisdictions.extend(jurisdictions)
        aggregate_law.extend(laws)
        aggregate_jurisdiction.extend(jurisdictions)

        features.finalize()
        segments[seg_id] = features

    finalized_durations = _finalize_numeric_map(aggregate_durations)
    aggregate_company_numbers_sorted = sorted(aggregate_company_numbers)

    return LxDocFeatures(
        segments=segments,
        labels=aggregate_labels,
        durations=finalized_durations,
        amounts=aggregate_amounts,
        company_numbers=aggregate_company_numbers_sorted,
        governing_law=aggregate_law,
        jurisdictions=aggregate_jurisdiction,
    )
