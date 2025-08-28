from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class RuleFormat(str, Enum):
    PYTHON = "python"
    YAML = "yaml"
    HYBRID = "hybrid"


@dataclass
class RuleSource:
    id: str
    pack: str
    format: RuleFormat
    path: Path
    py_path: Optional[Path] = None
    yaml_path: Optional[Path] = None

      # contract_review_app/rules_v2/types.py
"""Typing helpers for rules v2."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Protocol

from .models import FindingV2

__all__ = ["Rule", "LoadedRule"]


class Rule(Protocol):
    pack: str
    rule_id: str

    def evaluate(self, context: Dict[str, Any]) -> List[FindingV2]: ...


@dataclass
class LoadedRule:
    fmt: Literal["yaml", "python", "hybrid"]
    pack: str
    rule_id: str
    impl: Any
    path: Path