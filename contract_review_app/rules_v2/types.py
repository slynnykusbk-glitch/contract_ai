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

    @property
    def type(self) -> str:
        return self.format.value

    @property
    def rule_id(self) -> str:
        return self.id

    @property
    def fmt(self) -> str:
        return self.format.value
