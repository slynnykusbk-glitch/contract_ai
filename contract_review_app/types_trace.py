from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union


class TRange(TypedDict):
    start: int
    end: int


class TFeatureTokens(TypedDict, total=False):
    len: int


class TFeatureSeg(TypedDict, total=False):
    id: Union[int, str]
    range: TRange
    labels: List[str]
    entities: Dict[str, Any]
    tokens: TFeatureTokens


class TFeatureDoc(TypedDict, total=False):
    language: str
    length: int
    hash: str
    hints: List[Any]


class TFeatures(TypedDict, total=False):
    doc: TFeatureDoc
    segments: List[TFeatureSeg]


class TRulesetStats(TypedDict, total=False):
    loaded: int
    evaluated: int
    triggered: int


class TDispatchReasonPattern(TypedDict, total=False):
    kind: Literal["regex", "keyword"]
    offsets: List[List[int]]


class TDispatchReason(TypedDict, total=False):
    labels: List[str]
    patterns: List[TDispatchReasonPattern]
    gates: Dict[str, bool]


class TDispatchCandidate(TypedDict, total=False):
    rule_id: str
    gates: Dict[str, Any]
    gates_passed: bool
    triggers: Dict[str, Any]
    reason_not_triggered: Optional[str]
    reasons: List[TDispatchReason]


class TDispatch(TypedDict, total=False):
    ruleset: TRulesetStats
    candidates: List[TDispatchCandidate]


class TConstraintCheck(TypedDict, total=False):
    id: str
    scope: str
    result: Literal["pass", "fail", "skip"]
    details: Dict[str, Any]


class TConstraints(TypedDict, total=False):
    graph: Dict[str, Any]
    checks: List[TConstraintCheck]
    findings: List[Dict[str, Any]]


class TProposals(TypedDict, total=False):
    drafts: List[Dict[str, Any]]
    merged: List[Dict[str, Any]]


class TTraceMeta(TypedDict, total=False):
    risk_threshold: Literal["low", "medium", "high", "critical"]


class TCoverageSegment(TypedDict, total=False):
    index: int
    span: List[int]


class TCoverageZone(TypedDict, total=False):
    zone_id: str
    status: Literal["missing", "present", "rules_candidate", "rules_fired"]
    matched_labels: List[str]
    matched_entities: Dict[str, int]
    segments: List[TCoverageSegment]
    candidate_rules: List[str]
    fired_rules: List[str]
    missing_rules: List[str]


class TCoverage(TypedDict, total=False):
    version: int
    zones_total: int
    zones_present: int
    zones_candidates: int
    zones_fired: int
    details: List[TCoverageZone]
