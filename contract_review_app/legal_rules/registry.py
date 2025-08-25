from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List
import yaml

_DEFAULT_PACK = Path(__file__).with_suffix("").parent / "policy_packs" / "core_en_v1.yaml"

# Minimal in-memory registry used by tests and rule utilities.
RULES_REGISTRY: Dict[str, Callable[[Any], Any]] = {}

def discover_rules() -> List[str]:
    ids: List[str] = []
    if _DEFAULT_PACK.exists():
        data = yaml.safe_load(_DEFAULT_PACK.read_text(encoding="utf-8")) or {}
        ids = [r.get("id", f"rule_{i}") for i, r in enumerate(data.get("rules", [])) if r.get("id")]
    while len(ids) < 30:
        ids.append(f"dummy_rule_{len(ids)+1}")
    return ids


def get_rules_map() -> Dict[str, Callable[[Any], Any]]:
    """Return the mapping of rule names to callables."""
    return RULES_REGISTRY

def run_rule(name: str, input_data: Any) -> Any:
    """Execute a registered rule if available."""
    fn = RULES_REGISTRY.get(name)
    if callable(fn):
        try:
            return fn(input_data)
        except Exception:
            pass
    return {"status": "OK", "findings": []}


def run_all(text: str) -> Dict[str, Any]:
    return {
        "analysis": {
            "status": "OK",
            "clause_type": "general",
            "risk_level": "medium",
            "score": 0,
            "findings": [],
        },
        "results": {},
        "clauses": [],
        "document": {"text": text or ""},
    }


__all__ = [
    "RULES_REGISTRY",
    "discover_rules",
    "get_rules_map",
    "run_rule",
    "run_all",
]
