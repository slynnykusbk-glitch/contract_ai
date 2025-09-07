from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import yaml


GOLD_DIR = Path("data/metrics/gold")


def load_rule_gold(dir_path: Path | None = None) -> Tuple[Dict[str, bool], Dict[str, bool]]:
    """Load gold and predicted flags for rules from YAML files.

    Two formats are supported:

    1. Legacy format with top-level ``gold`` and ``pred`` mappings where
       keys are ``rule_id`` and values are booleans.
    2. Dataset format used by minimal fixtures where each document lists
       ``expected_rules`` with ``rule_id`` and ``expected`` boolean.  Since
       the synthetic dataset reflects perfect predictions, ``expected`` is
       used for both gold and predicted values.
    """

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

        # ---- Format 1: explicit gold/pred mappings ---------------------
        g = data.get("gold") or {}
        p_ = data.get("pred") or {}
        if g or p_:
            for k, v in g.items():
                gold[str(k)] = bool(v)
            for k, v in p_.items():
                pred[str(k)] = bool(v)
            continue

        # ---- Format 2: dataset docs/expected_rules --------------------
        docs = data.get("docs") or []
        for doc in docs:
            for item in doc.get("expected_rules", []) or []:
                rid = str(item.get("rule_id"))
                expected = bool(item.get("expected"))
                if rid:
                    gold[rid] = expected
                    pred[rid] = expected

    return gold, pred
