"""Utility for auditing rule definitions.

This script scans YAML rule packs and Python rule modules to generate an
inventory file. The resulting JSON contains a list of rules with basic
metadata which is helpful for quickly checking for duplicate identifiers or
missing fields.  The tool is intentionally lightweight and avoids importing
heavy application modules so that it can run in CI without side effects.

Usage::

    python tools/rules_audit.py

The command writes ``docs/rules_inventory.json`` relative to the repository
root.  The inventory is sorted for stable output so the file can be checked in
to version control.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_list(value: Iterable | None) -> List[str]:
    if not value:
        return []
    return [str(v) for v in value if v is not None]


def _extract_triggers(triggers: Dict) -> Dict[str, List[str]]:
    """Normalize trigger specifications into ``{kind: [patterns]}``."""

    out: Dict[str, List[str]] = {"any": [], "all": [], "regex": []}
    if not isinstance(triggers, dict):
        return out
    for key in out.keys():
        items = triggers.get(key) or []
        patterns: List[str] = []
        for it in items:
            if isinstance(it, dict):
                pat = it.get("regex")
            else:
                pat = it
            if pat:
                patterns.append(str(pat))
        out[key] = patterns
    # drop empty keys for compactness
    return {k: v for k, v in out.items() if v}


def _iter_rule_docs(path: Path) -> Iterable[Dict]:
    """Yield rule dictionaries from a YAML file.

    The repository historically used several slightly different YAML layouts.
    This helper normalises the most common shapes by looking for ``rules`` or
    ``rule`` keys and falling back to treating the document itself as a rule
    object.
    """

    raw_text = path.read_text(encoding="utf-8")
    for doc in yaml.safe_load_all(raw_text):
        if not doc:
            continue
        if isinstance(doc, dict) and doc.get("rule"):
            yield from _iter_rule_list([doc["rule"]])
        elif isinstance(doc, dict) and doc.get("rules"):
            yield from _iter_rule_list(doc.get("rules") or [])
        elif isinstance(doc, list):
            yield from _iter_rule_list(doc)
        elif isinstance(doc, dict):
            yield doc


def _iter_rule_list(items: Iterable) -> Iterable[Dict]:
    for item in items:
        if isinstance(item, dict):
            yield item


def _collect_from_yaml(path: Path) -> List[Dict]:
    rules: List[Dict] = []
    for raw in _iter_rule_docs(path):
        rule_id = str(raw.get("id") or raw.get("rule_id") or "").strip()
        if not rule_id:
            continue
        doc_types = _as_list(
            raw.get("doc_types") or (raw.get("scope", {}) or {}).get("doc_types")
        )
        trig = _extract_triggers(raw.get("triggers") or {})
        requires = _as_list(
            raw.get("requires_clause") or raw.get("requires_clause_hit")
        )
        # many legacy rules use ``scope.clauses`` to signal required clause
        if not requires:
            requires = _as_list((raw.get("scope", {}) or {}).get("clauses"))
        rules.append(
            {
                "rule_id": rule_id,
                "pack": str(path.relative_to(ROOT)),
                "doc_types": doc_types,
                "triggers": trig,
                "requires_clause": requires,
                "deprecated": bool(raw.get("deprecated")),
            }
        )
    return rules


def _collect_from_python(path: Path) -> List[Dict]:
    """Extract rule identifiers from a Python module.

    The heuristic is purposely simple: any string assigned to a variable named
    ``RULE_ID`` or ``RULE_IDS`` is picked up.  This covers small helper modules
    used in tests; if no identifiers are found an empty list is returned.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    rules: List[Dict] = []
    import re

    ids: List[str] = []
    single = re.findall(r"RULE_ID\s*=\s*['\"]([^'\"]+)['\"]", text)
    multiple = re.findall(r"RULE_IDS\s*=\s*\[([^\]]+)\]", text)
    for grp in multiple:
        ids.extend(re.findall(r"['\"]([^'\"]+)['\"]", grp))
    ids.extend(single)
    for rid in ids:
        rules.append(
            {
                "rule_id": rid,
                "pack": str(path.relative_to(ROOT)),
                "doc_types": [],
                "triggers": {},
                "requires_clause": [],
                "deprecated": False,
            }
        )
    return rules


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def collect_rules() -> List[Dict]:
    """Collect rule metadata from YAML packs and Python modules."""

    yaml_dirs = [
        ROOT / "core" / "rules",
        ROOT / "contract_review_app" / "legal_rules",
    ]
    rules: List[Dict] = []
    for base in yaml_dirs:
        if base.exists():
            for path in base.rglob("*.yml"):
                rules.extend(_collect_from_yaml(path))
            for path in base.rglob("*.yaml"):
                rules.extend(_collect_from_yaml(path))

    for path in ROOT.rglob("rules.py"):
        rules.extend(_collect_from_python(path))

    # flag duplicates
    counts: Dict[str, int] = {}
    for r in rules:
        rid = r["rule_id"]
        counts[rid] = counts.get(rid, 0) + 1
    for r in rules:
        r["duplicates"] = counts.get(r["rule_id"], 0) > 1

    rules.sort(key=lambda x: (x["rule_id"], x["pack"]))
    return rules


def main() -> None:
    data = collect_rules()
    out_path = ROOT / "docs" / "rules_inventory.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
