#!/usr/bin/env python3
"""Generate inventory of legal rules and save CSV/JSON summaries."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"


def iter_rule_files() -> List[Path]:
    bases = [ROOT / "contract_review_app" / "legal_rules", ROOT / "core" / "rules"]
    for base in bases:
        for ext in ("*.yaml", "*.yml"):
            yield from base.rglob(ext)


def build_inventory() -> List[Dict[str, object]]:
    rows = []
    for path in iter_rule_files():
        try:
            docs = list(yaml.safe_load_all(path.read_text()))
        except Exception:
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            rule = doc.get("rule")
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id:
                continue
            scope = rule.get("scope", {})
            juris = scope.get("jurisdiction", []) or []
            doc_types = scope.get("doc_types", []) or []
            triggers = rule.get("triggers", {})
            trig_present = bool(triggers.get("any") or triggers.get("all"))
            checks = rule.get("checks", [])
            checks_present = bool(checks)
            rows.append(
                {
                    "pack": str(path.relative_to(ROOT)),
                    "rule_id": rule_id,
                    "schema": doc.get("schema"),
                    "doc_types": doc_types,
                    "jurisdictions": juris,
                    "has_triggers": trig_present,
                    "has_checks": checks_present,
                }
            )
    return rows


def main() -> None:
    rows = build_inventory()
    DOCS_DIR.mkdir(exist_ok=True)
    json_path = DOCS_DIR / "rules_inventory.json"
    csv_path = DOCS_DIR / "rules_inventory.csv"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True))
    fieldnames = [
        "pack",
        "rule_id",
        "schema",
        "doc_types",
        "jurisdictions",
        "has_triggers",
        "has_checks",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rec = row.copy()
            rec["doc_types"] = ";".join(rec["doc_types"])
            rec["jurisdictions"] = ";".join(rec["jurisdictions"])
            writer.writerow(rec)


if __name__ == "__main__":
    main()
