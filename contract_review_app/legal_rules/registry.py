# minimal registry that prefers YAML pack
from __future__ import annotations
from typing import Any, List, Dict
from pathlib import Path
from .yaml_runtime import load_pack, evaluate

_DEFAULT_PACK = Path(__file__).with_suffix("").parent / "policy_packs" / "core_en_v1.yaml"

def discover_rules() -> List[str]:
    # Return stable ids for diagnostics
    if _DEFAULT_PACK.exists():
        data = load_pack(_DEFAULT_PACK)
        return [r.id for r in data.rules]
    return []

def run_all(text: str) -> Dict[str, Any]:
    if _DEFAULT_PACK.exists():
        pack = load_pack(_DEFAULT_PACK)
        f = evaluate(text, pack)
        return {
            "analysis": {
                "status": "OK",
                "clause_type": "general",
                "risk_level": "medium",
                "score": 0,
                "findings": [vars(x) for x in f],
            },
            "results": {},
            "clauses": [],
            "document": {"text": text or ""},
        }
    # fallback empty
    return {"analysis": {"status":"OK","clause_type":"general","risk_level":"medium","score":0,"findings":[]},
            "results":{},"clauses":[],"document":{"text":text or ""}}
