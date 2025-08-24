from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import re
import yaml


@dataclass
class Rule:
    """Simple representation of a legal rule."""

    id: str
    clause_type: str
    severity: str
    patterns: List[re.Pattern]
    advice: Optional[str] = None


_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_PACK = _BASE_DIR / "policy_packs" / "core_en_v1.yaml"


def load_yaml_policy_pack(path: str | Path) -> List[Rule]:
    """Load rules from a YAML policy pack."""

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out: List[Rule] = []
    for r in data.get("rules", []) or []:
        pats = [re.compile(p, re.IGNORECASE | re.MULTILINE | re.DOTALL) for p in r.get("patterns", [])]
        out.append(
            Rule(
                id=str(r.get("id", "")),
                clause_type=str(r.get("clause_type", "")),
                severity=str(r.get("severity", "medium")),
                patterns=pats,
                advice=r.get("advice"),
            )
        )
    return out


def discover_rules(include_yaml: bool = True) -> List[Rule]:
    """Discover available rules. Currently only YAML policy packs are supported."""

    rules: List[Rule] = []
    if include_yaml and _DEFAULT_PACK.exists():
        rules.extend(load_yaml_policy_pack(_DEFAULT_PACK))
    return rules

