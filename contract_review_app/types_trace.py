from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict, Union


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


class TDispatch(TypedDict, total=False):
    ruleset: TRulesetStats
    candidates: List[Dict[str, Any]]


class TConstraintCheck(TypedDict, total=False):
    id: str
    scope: str
    result: Literal["pass", "fail", "skip"]
    details: Dict[str, Any]


class TConstraints(TypedDict, total=False):
    checks: List[TConstraintCheck]


class TProposals(TypedDict, total=False):
    drafts: List[Dict[str, Any]]
    merged: List[Dict[str, Any]]


class TTraceMeta(TypedDict, total=False):
    risk_threshold: Literal["low", "medium", "high", "critical"]
