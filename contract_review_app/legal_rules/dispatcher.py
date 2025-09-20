"""Lightweight L1 dispatcher narrowing candidate YAML rules per segment."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Dict, Iterable, List, MutableMapping, Optional, Set, Tuple

from contract_review_app.core.lx_types import LxFeatureSet, LxSegment

from . import loader


@dataclass(frozen=True)
class RuleRef:
    """Reference to a rule suggested for evaluation."""

    rule_id: str
    reasons: Tuple[str, ...] = ()


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


def _collect_from_index(
    index: MutableMapping[str, Set[str]],
    keys: Iterable[str],
    reason: str,
    acc: MutableMapping[str, Set[str]],
) -> None:
    for key in keys:
        if not key:
            continue
        vals = index.get(key)
        if not vals:
            continue
        for rule_id in vals:
            acc.setdefault(rule_id, set()).add(reason)


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

    reasons: Dict[str, Set[str]] = {}

    labels = { _normalize_token(lbl) for lbl in (feats.labels or []) }
    clause_type = _normalize_token(segment.clause_type or "")
    if clause_type:
        labels.add(clause_type)

    for label in sorted(labels):
        clause_targets = _LABEL_TO_CLAUSES.get(label, set())
        if clause_targets:
            _collect_from_index(
                clause_index,
                (ct for ct in clause_targets),
                f"label:{label}",
                reasons,
            )
        keywords = _LABEL_KEYWORDS.get(label, set())
        if keywords:
            _collect_from_index(
                token_index,
                keywords,
                f"keyword:{label}",
                reasons,
            )

    if feats.durations:
        _collect_from_index(token_index, {"day", "days", "payment", "term"}, "duration", reasons)

    if feats.amounts:
        _collect_from_index(token_index, {"amount", "fee", "charge", "price"}, "amount", reasons)

    for signal in feats.law_signals or []:
        tokens = _tokenize(signal)
        _collect_from_index(token_index, tokens, "law", reasons)

    if feats.jurisdiction:
        juris_tokens = {feats.jurisdiction.lower()} | _tokenize(feats.jurisdiction)
        _collect_from_index(jurisdiction_index, juris_tokens, "jurisdiction", reasons)
        _collect_from_index(token_index, juris_tokens, "jurisdiction", reasons)

    for token in _features_from_segment(segment):
        _collect_from_index(token_index, {token}, f"text:{token}", reasons)

    if not reasons:
        if clause_type:
            _collect_from_index(clause_index, {clause_type}, f"clause:{clause_type}", reasons)

    if not reasons:
        return []

    rule_refs = [
        RuleRef(rule_id=rid, reasons=tuple(sorted(reason_set)))
        for rid, reason_set in reasons.items()
    ]
    rule_refs.sort(key=lambda ref: ref.rule_id)
    return rule_refs
