from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict


class TFeatures(TypedDict, total=False):
    doc: Dict[str, Any]
    segments: List[Dict[str, Any]]


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
