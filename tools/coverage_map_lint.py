#!/usr/bin/env python3
"""Validate the coverage map specification."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_app.analysis.labels_taxonomy import LABELS_CANON  # noqa: E402
from contract_review_app.legal_rules import coverage_map, loader  # noqa: E402
from contract_review_app.legal_rules.coverage_zones import (  # noqa: E402
    HIGH_IMPORTANCE_ZONES,
    SERVICE_LABEL_IDS,
    ZONE_ENTITY_MATRIX,
)


def _bool_map(mapping: Mapping[str, object]) -> dict[str, bool]:
    return {key: bool(mapping.get(key, False)) for key in sorted(mapping)}


def run(strict: bool = False) -> int:
    coverage_map.invalidate_cache()
    cmap = coverage_map.load_coverage_map()
    if cmap is None:
        print("Failed to load coverage map", file=sys.stderr)
        return 1

    zones_total = len(cmap.zones)
    strict_mode = strict or os.getenv("FEATURE_COVERAGE_LINT_STRICT") == "1"

    issues: list[str] = []
    if zones_total < 30:
        issues.append("Coverage map must contain at least 30 zones")

    used_labels: set[str] = set()

    for zone in cmap.zones:
        used_labels.update(zone.label_any)
        if zone.zone_id in HIGH_IMPORTANCE_ZONES and len(zone.label_any) < 5:
            issues.append(
                f"Zone '{zone.zone_id}' must declare at least 5 label selectors"
            )
        expected_entities = ZONE_ENTITY_MATRIX.get(zone.zone_id)
        if expected_entities is not None:
            current = _bool_map(zone.entity_selectors)
            expected = _bool_map(expected_entities)
            if current != expected:
                issues.append(
                    f"Zone '{zone.zone_id}' entity selectors {current} != {expected}"
                )
        if not (zone.label_any or zone.label_all or zone.label_none):
            issues.append(f"Zone '{zone.zone_id}' must define at least one selector")
        if zone.required and not zone.rule_ids:
            issues.append(f"Zone '{zone.zone_id}' is required but has no rules mapped")

    rules = loader.load_rules()
    rule_ids = {
        str(rule.get("id") or rule.get("rule_id") or "").strip()
        for rule in rules
        if str(rule.get("id") or rule.get("rule_id") or "").strip()
    }
    total_rules = len(rule_ids)
    covered_rules = {
        rule_id for rule_id in cmap.rule_index.keys() if rule_id in rule_ids
    }
    rule_ratio = len(covered_rules) / total_rules if total_rules else 1.0
    if rule_ratio < 0.8:
        issues.append(
            f"Only {len(covered_rules)} of {total_rules} rules have coverage entries"
        )

    taxonomy_labels = set(LABELS_CANON.keys()) - set(SERVICE_LABEL_IDS)
    labels_used = used_labels.intersection(taxonomy_labels)
    label_ratio = len(labels_used) / len(taxonomy_labels) if taxonomy_labels else 1.0
    if label_ratio < 0.7:
        issues.append(
            f"Only {len(labels_used)} of {len(taxonomy_labels)} taxonomy labels used"
        )

    unused_labels = sorted(taxonomy_labels - labels_used)

    summary = {
        "version": cmap.version,
        "zones_total": zones_total,
        "labels_used": len(labels_used),
        "labels_total": len(taxonomy_labels),
        "labels_ratio": round(label_ratio, 4),
        "rules_covered": len(covered_rules),
        "rules_total": total_rules,
        "rules_ratio": round(rule_ratio, 4),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if unused_labels:
        print("\nTop unused labels:")
        for label in unused_labels[:10]:
            print(f"  - {label}")

    if issues:
        print("\nIssues detected:")
        for item in issues:
            print(f"  - {item}")
        if strict_mode:
            return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate coverage map")
    parser.add_argument("--strict", action="store_true", help="Enforce strict checks")
    args = parser.parse_args()
    raise SystemExit(run(strict=args.strict))


if __name__ == "__main__":
    main()
