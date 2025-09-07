from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import yaml


GOLD_DIR = Path("data/metrics/gold")


def load_rule_gold(dir_path: Path | None = None) -> Tuple[Dict[str, bool], Dict[str, bool]]:
    """Load gold and predicted flags for rules from YAML files."""
    if dir_path is None:
        dir_path = GOLD_DIR
    gold: Dict[str, bool] = {}
    pred: Dict[str, bool] = {}
    if not dir_path.exists():
        return gold, pred
    for p in dir_path.glob("*.yaml"):
        try:
            data = yaml.safe_load(p.read_text()) or {}
        except Exception:
            continue
        g = data.get("gold") or {}
        p_ = data.get("pred") or {}
        for k, v in g.items():
            gold[str(k)] = bool(v)
        for k, v in p_.items():
            pred[str(k)] = bool(v)
    return gold, pred
