from __future__ import annotations

from typing import Any

from .types_trace import TConstraints, TDispatch, TFeatures, TProposals


def build_features(*args: Any, **kwargs: Any) -> TFeatures:
    return {}


def build_dispatch(*args: Any, **kwargs: Any) -> TDispatch:
    return {}


def build_constraints(*args: Any, **kwargs: Any) -> TConstraints:
    return {}


def build_proposals(*args: Any, **kwargs: Any) -> TProposals:
    return {}
