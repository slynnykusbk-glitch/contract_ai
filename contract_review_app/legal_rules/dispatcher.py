"""Lightweight L1 dispatcher narrowing candidate YAML rules per segment."""

from __future__ import annotations

import math
from decimal import Decimal
from dataclasses import dataclass
from functools import lru_cache
import re
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from typing import Literal

from contract_review_app.core.lx_types import LxFeatureSet, LxSegment

from . import loader


@dataclass(frozen=True)
class ReasonPattern:
    kind: Literal["regex", "keyword"]
    offsets: Tuple[Tuple[int, int], ...] = ()

    def to_json(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "offsets": [[int(start), int(end)] for start, end in self.offsets],
        }


@dataclass(frozen=True)
class ReasonAmount:
    currency: str
    value: int | float
    offsets: Tuple[Tuple[int, int], ...] = ()

    def to_json(self) -> Dict[str, Any]:
        value = self.value
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return {
            "ccy": self.currency,
            "value": value,
            "offsets": [[int(start), int(end)] for start, end in self.offsets],
        }


@dataclass(frozen=True)
class ReasonDuration:
    unit: str
    value: int
    offsets: Tuple[Tuple[int, int], ...] = ()

    def to_json(self) -> Dict[str, Any]:
        return {
            "unit": self.unit,
            "value": int(self.value),
            "offsets": [[int(start), int(end)] for start, end in self.offsets],
        }


@dataclass(frozen=True)
class ReasonCodeRef:
    code: str
    offsets: Tuple[Tuple[int, int], ...] = ()

    def to_json(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "offsets": [[int(start), int(end)] for start, end in self.offsets],
        }


@dataclass(frozen=True)
class ReasonPayload:
    labels: Tuple[str, ...] = ()
    patterns: Tuple[ReasonPattern, ...] = ()
    gates: Tuple[Tuple[str, bool], ...] = ()
    amounts: Tuple["ReasonAmount", ...] = ()
    durations: Tuple["ReasonDuration", ...] = ()
    law: Tuple["ReasonCodeRef", ...] = ()
    jurisdiction: Tuple["ReasonCodeRef", ...] = ()

    def identity(
        self,
    ) -> Tuple[
        Tuple[str, ...],
        Tuple[Tuple[str, Tuple[Tuple[int, int], ...]], ...],
        Tuple[Tuple[str, bool], ...],
        Tuple[Tuple[str, Any], ...],
    ]:
        label_key = tuple(sorted(self.labels))
        pattern_key = tuple(
            (pattern.kind, tuple(pattern.offsets)) for pattern in self.patterns
        )
        gates_key = tuple(sorted(self.gates))
        data_key = tuple(
            [
                ("amounts", tuple((entry.currency, entry.value, entry.offsets) for entry in self.amounts)),
                ("durations", tuple((entry.unit, entry.value, entry.offsets) for entry in self.durations)),
                ("law", tuple((entry.code, entry.offsets) for entry in self.law)),
                (
                    "jurisdiction",
                    tuple((entry.code, entry.offsets) for entry in self.jurisdiction),
                ),
            ]
        )
        return label_key, pattern_key, gates_key, data_key

    def to_json(self) -> Dict[str, Any]:
        return {
            "labels": list(dict.fromkeys(sorted(self.labels))),
            "patterns": [pattern.to_json() for pattern in self.patterns],
            "gates": {name: bool(flag) for name, flag in self.gates},
            "amounts": [amount.to_json() for amount in self.amounts],
            "durations": [duration.to_json() for duration in self.durations],
            "law": [entry.to_json() for entry in self.law],
            "jurisdiction": [entry.to_json() for entry in self.jurisdiction],
        }


@dataclass(frozen=True)
class RuleRef:
    """Reference to a rule suggested for evaluation."""

    rule_id: str
    reasons: Tuple[ReasonPayload, ...] = ()


def _coerce_reason_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        normalized = text.replace(",", "")
        try:
            if "." in normalized:
                number = float(normalized)
            else:
                number = int(normalized)
        except ValueError:
            return None
        if isinstance(number, float) and (math.isnan(number) or math.isinf(number)):
            return None
        return number
    if isinstance(value, Decimal):
        integral = value.to_integral_value()
        if integral == value:
            return int(integral)
        return float(value)
    return None


def _coerce_reason_int(value: Any) -> Optional[int]:
    number = _coerce_reason_number(value)
    if number is None:
        return None
    if isinstance(number, float):
        if not number.is_integer():
            return None
        number = int(number)
    return int(number)


def _coerce_offsets(entry: Mapping[str, Any]) -> Tuple[Tuple[int, int], ...]:
    start_raw = entry.get("start")
    end_raw = entry.get("end")
    try:
        start = int(start_raw)
        end = int(end_raw)
    except (TypeError, ValueError):
        return ()
    if end < start:
        return ()
    return ((start, end),)


def _entity_entries(feats: Optional[LxFeatureSet], key: str) -> Sequence[Mapping[str, Any]]:
    if feats is None:
        return ()
    entities = getattr(feats, "entities", None)
    if not isinstance(entities, Mapping):
        return ()
    raw_entries = entities.get(key)
    if not isinstance(raw_entries, Iterable) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        return ()
    collected: list[Mapping[str, Any]] = []
    for item in raw_entries:
        if isinstance(item, Mapping):
            collected.append(item)
    return tuple(collected)


def _reason_amounts(feats: Optional[LxFeatureSet]) -> Tuple[ReasonAmount, ...]:
    entries: list[ReasonAmount] = []
    for entry in _entity_entries(feats, "amounts"):
        offsets = _coerce_offsets(entry)
        if not offsets:
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        currency_raw = value.get("currency")
        amount_raw = value.get("amount")
        if not isinstance(currency_raw, str) or not currency_raw.strip():
            continue
        amount = _coerce_reason_number(amount_raw)
        if amount is None:
            continue
        currency = currency_raw.strip().upper()
        entries.append(ReasonAmount(currency=currency, value=amount, offsets=offsets))
    if not entries:
        return ()
    return tuple(sorted(entries, key=lambda item: (item.offsets, item.currency, item.value)))


def _reason_durations(feats: Optional[LxFeatureSet]) -> Tuple[ReasonDuration, ...]:
    entries: list[ReasonDuration] = []
    for entry in _entity_entries(feats, "durations"):
        offsets = _coerce_offsets(entry)
        if not offsets:
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        number: Optional[int] = None
        unit: Optional[str] = None
        for candidate in ("days", "weeks", "months", "years"):
            candidate_value = _coerce_reason_int(value.get(candidate))
            if candidate_value is not None:
                number = candidate_value
                unit = candidate
                break
        if number is None:
            duration_iso = value.get("duration")
            if isinstance(duration_iso, str) and duration_iso.upper().startswith("P"):
                code = duration_iso[-1].upper()
                unit_map = {"D": "days", "W": "weeks", "M": "months", "Y": "years"}
                try:
                    number_candidate = int(duration_iso[1:-1])
                except (TypeError, ValueError):
                    number_candidate = None
                if number_candidate is not None and code in unit_map:
                    number = number_candidate
                    unit = unit_map[code]
        if number is None or unit is None:
            continue
        entries.append(ReasonDuration(unit=unit, value=number, offsets=offsets))
    if not entries:
        return ()
    return tuple(sorted(entries, key=lambda item: (item.offsets, item.unit, item.value)))


def _reason_codes(
    feats: Optional[LxFeatureSet], key: str
) -> Tuple[ReasonCodeRef, ...]:
    entries: list[ReasonCodeRef] = []
    for entry in _entity_entries(feats, key):
        offsets = _coerce_offsets(entry)
        if not offsets:
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        code_raw = value.get("code")
        if not isinstance(code_raw, str) or not code_raw.strip():
            continue
        code = code_raw.strip().upper()
        entries.append(ReasonCodeRef(code=code, offsets=offsets))
    if not entries:
        return ()
    return tuple(sorted(entries, key=lambda item: (item.offsets, item.code)))


def _normalize_token(token: str) -> str:
    token = token.lower()
    return re.sub(r"[^a-z0-9]+", "_", token).strip("_")


def _tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@lru_cache(maxsize=1)
def _rule_index() -> Tuple[
    Tuple[Dict[str, str], ...],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
]:
    """Build cached indexes for rule metadata lookup."""

    loader.load_rule_packs()
    rules: List[Dict[str, str]] = []
    token_index: Dict[str, Set[str]] = {}
    clause_index: Dict[str, Set[str]] = {}
    jurisdiction_index: Dict[str, Set[str]] = {}

    for spec in loader.load_rules():
        rule_id = str(spec.get("id") or spec.get("rule_id") or "").strip()
        if not rule_id:
            continue
        clause_type = str(spec.get("clause_type") or "").strip().lower()
        title = str(spec.get("title") or spec.get("Title") or "")
        pack = str(spec.get("pack") or "")
        requires_clause = spec.get("requires_clause") or []
        jurisdiction = spec.get("jurisdiction") or []

        fields = " ".join(
            f
            for f in [rule_id, title, clause_type, pack, " ".join(requires_clause)]
            if f
        )
        tokens = _tokenize(fields)
        for token in tokens:
            token_index.setdefault(token, set()).add(rule_id)

        if clause_type:
            clause_index.setdefault(clause_type, set()).add(rule_id)
        for req in requires_clause:
            norm_req = _normalize_token(req)
            if norm_req:
                clause_index.setdefault(norm_req, set()).add(rule_id)

        for juris in jurisdiction:
            juris_token = juris.lower()
            jurisdiction_index.setdefault(juris_token, set()).add(rule_id)

        rules.append({"id": rule_id, "clause_type": clause_type, "title": title})

    return tuple(rules), token_index, clause_index, jurisdiction_index


_LABEL_TO_CLAUSES: Dict[str, Set[str]] = {
    "payment": {"payment", "invoice", "billing", "setoff", "rebate", "tax"},
    "term": {"term", "termination", "duration", "renewal"},
    "liability": {"liability", "indemnity", "damages", "limitation"},
    "confidentiality": {"confidentiality", "nda", "confidential"},
    "indemnity": {"indemnity", "liability"},
    "governinglaw": {"governing_law", "law"},
    "jurisdiction": {"jurisdiction"},
    "dispute": {"dispute", "litigation", "arbitration"},
    "ip": {"intellectual_property", "ip", "ipr", "intellectual"},
    "notices": {"notices", "notification", "notice"},
    "taxes": {"tax", "taxes", "withholding", "vat"},
    "setoff": {"setoff", "set_off", "payment"},
    "interest": {"interest", "payment"},
    "price": {"pricing", "payment", "price"},
    "sla": {"sla", "service_level", "service_levels"},
    "kpi": {"kpi", "service_level", "metrics"},
    "acceptance": {"acceptance", "delivery", "inspection"},
    "boilerplate": {"boilerplate", "general", "miscellaneous"},
}

_LABEL_KEYWORDS: Dict[str, Set[str]] = {
    "payment": {"payment", "invoice", "pay", "interest", "setoff", "charge"},
    "term": {"term", "notice", "duration", "renewal", "expire"},
    "liability": {"liability", "damages", "cap", "limit", "limitation", "indemnity"},
    "confidentiality": {"confidential", "nda", "non", "disclosure"},
    "indemnity": {"indemnity", "defend", "hold", "harmless"},
    "governinglaw": {"governing", "law", "laws", "england"},
    "jurisdiction": {"jurisdiction", "courts", "forum"},
    "dispute": {"dispute", "arbitration", "litigation", "mediati"},
    "ip": {"intellectual", "property", "ip", "ipr", "licence", "license"},
    "notices": {"notice", "notify", "address", "delivery"},
    "taxes": {"tax", "vat", "withhold", "gross", "ddp"},
    "setoff": {"setoff", "set", "off", "deduct"},
    "interest": {"interest", "late", "payment"},
    "price": {"price", "pricing", "rates", "charges", "fees"},
    "sla": {"sla", "service", "level", "availability"},
    "kpi": {"kpi", "performance", "target", "metric"},
    "acceptance": {"acceptance", "accept", "inspection", "testing"},
    "boilerplate": {"hereby", "thereof", "agreement", "entire"},
}

_TEXT_TOKEN_ALLOWLIST: Set[str] = {
    "payment",
    "invoice",
    "interest",
    "term",
    "termination",
    "notice",
    "liability",
    "indemnity",
    "confidential",
    "jurisdiction",
    "law",
    "governing",
    "dispute",
    "arbitration",
    "tax",
    "vat",
    "price",
    "charge",
    "acceptance",
    "inspection",
    "ip",
    "intellectual",
    "sla",
    "kpi",
    "uk",
    "england",
    "wales",
    "scotland",
}


def _make_reason(
    *,
    labels: Iterable[str] = (),
    pattern_kind: Optional[Literal["regex", "keyword"]] = None,
    gates: Optional[Dict[str, bool]] = None,
    pattern_offsets: Optional[Iterable[Tuple[int, int]]] = None,
    amounts: Optional[Iterable[ReasonAmount]] = None,
    durations: Optional[Iterable[ReasonDuration]] = None,
    law: Optional[Iterable[ReasonCodeRef]] = None,
    jurisdiction: Optional[Iterable[ReasonCodeRef]] = None,
) -> ReasonPayload:
    label_items = tuple(sorted({str(lbl).strip() for lbl in labels if str(lbl).strip()}))
    patterns: Tuple[ReasonPattern, ...] = ()
    if pattern_kind is not None:
        offsets: Tuple[Tuple[int, int], ...] = ()
        if pattern_offsets:
            collected: list[Tuple[int, int]] = []
            seen: set[Tuple[int, int]] = set()
            for start, end in pattern_offsets:
                try:
                    start_int = int(start)
                    end_int = int(end)
                except (TypeError, ValueError):
                    continue
                if end_int < start_int:
                    continue
                span = (start_int, end_int)
                if span in seen:
                    continue
                seen.add(span)
                collected.append(span)
            if collected:
                offsets = tuple(sorted(collected))
        patterns = (ReasonPattern(kind=pattern_kind, offsets=offsets),)
    gate_items: Tuple[Tuple[str, bool], ...] = ()
    if gates:
        gate_items = tuple((str(name), bool(value)) for name, value in sorted(gates.items()))
    amount_items = tuple(amounts) if amounts else ()
    duration_items = tuple(durations) if durations else ()
    law_items = tuple(law) if law else ()
    juris_items = tuple(jurisdiction) if jurisdiction else ()
    return ReasonPayload(
        labels=label_items,
        patterns=patterns,
        gates=gate_items,
        amounts=amount_items,
        durations=duration_items,
        law=law_items,
        jurisdiction=juris_items,
    )


def _collect_from_index(
    index: MutableMapping[str, Set[str]],
    keys: Iterable[str],
    reason_factory: Callable[[str], Optional[ReasonPayload]],
    acc: MutableMapping[str, Dict[Tuple[Any, ...], ReasonPayload]],
) -> None:
    for key in keys:
        if not key:
            continue
        vals = index.get(key)
        if not vals:
            continue
        payload = reason_factory(key)
        if payload is None:
            continue
        reason_key = payload.identity()
        for rule_id in vals:
            rid = str(rule_id)
            acc.setdefault(rid, {})
            if reason_key not in acc[rid]:
                acc[rid][reason_key] = payload


def _features_from_segment(segment: LxSegment) -> Set[str]:
    tokens = _tokenize(segment.combined_text())
    return {t for t in tokens if t in _TEXT_TOKEN_ALLOWLIST}


def select_candidate_rules(
    segment: LxSegment,
    feats: Optional[LxFeatureSet],
) -> List[RuleRef]:
    """Return rule references relevant to *segment* based on L0 features."""

    if feats is None:
        feats = LxFeatureSet()

    (_, token_index, clause_index, jurisdiction_index) = _rule_index()

    reasons: Dict[str, Dict[Tuple[Any, ...], ReasonPayload]] = {}

    labels = { _normalize_token(lbl) for lbl in (feats.labels or []) }
    clause_type = _normalize_token(segment.clause_type or "")
    if clause_type:
        labels.add(clause_type)

    amount_entries = _reason_amounts(feats)
    duration_entries = _reason_durations(feats)
    law_entries = _reason_codes(feats, "law")
    jurisdiction_entries = _reason_codes(feats, "jurisdiction")

    for label in sorted(labels):
        clause_targets = _LABEL_TO_CLAUSES.get(label, set())
        if clause_targets:
            _collect_from_index(
                clause_index,
                (ct for ct in clause_targets),
                lambda _clause, lbl=label: _make_reason(labels={lbl}),
                reasons,
            )
        keywords = _LABEL_KEYWORDS.get(label, set())
        if keywords:
            _collect_from_index(
                token_index,
                keywords,
                lambda _kw, lbl=label: _make_reason(
                    labels={lbl}, pattern_kind="keyword"
                ),
                reasons,
            )

    if feats.durations or duration_entries:
        duration_reason = _make_reason(
            labels={"duration"},
            durations=duration_entries,
        )
        _collect_from_index(
            token_index,
            {"day", "days", "payment", "term"},
            lambda _token: duration_reason,
            reasons,
        )

    if feats.amounts or amount_entries:
        amount_reason = _make_reason(
            labels={"amount"},
            amounts=amount_entries,
        )
        _collect_from_index(
            token_index,
            {"amount", "fee", "charge", "price"},
            lambda _token: amount_reason,
            reasons,
        )

    law_tokens: Set[str] = set()
    for signal in feats.law_signals or []:
        law_tokens.update(_tokenize(signal))
    for entry in law_entries:
        law_tokens.update(_tokenize(entry.code))
    if law_tokens:
        law_reason = _make_reason(
            labels={"law"},
            pattern_kind="keyword",
            law=law_entries,
        )
        _collect_from_index(token_index, law_tokens, lambda _token: law_reason, reasons)

    juris_tokens: Set[str] = set()
    if feats.jurisdiction:
        juris_tokens.update({feats.jurisdiction.lower()})
        juris_tokens.update(_tokenize(feats.jurisdiction))
    for entry in jurisdiction_entries:
        juris_tokens.update(_tokenize(entry.code))
    if juris_tokens:
        juris_reason = _make_reason(
            labels={"jurisdiction"},
            jurisdiction=jurisdiction_entries,
        )
        _collect_from_index(
            jurisdiction_index,
            juris_tokens,
            lambda _token: juris_reason,
            reasons,
        )
        _collect_from_index(
            token_index,
            juris_tokens,
            lambda _token: juris_reason,
            reasons,
        )

    for token in _features_from_segment(segment):
        _collect_from_index(
            token_index,
            {token},
            lambda key: _make_reason(labels={key}, pattern_kind="keyword"),
            reasons,
        )

    if not reasons:
        if clause_type:
            _collect_from_index(
                clause_index,
                {clause_type},
                lambda key: _make_reason(labels={key}),
                reasons,
            )

    if not reasons:
        return []

    rule_refs = [
        RuleRef(
            rule_id=rid,
            reasons=tuple(
                sorted(
                    reason_map.values(),
                    key=lambda payload: payload.identity(),
                )
            ),
        )
        for rid, reason_map in reasons.items()
    ]
    rule_refs.sort(key=lambda ref: ref.rule_id)
    return rule_refs
