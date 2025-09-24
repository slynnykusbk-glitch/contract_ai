#!/usr/bin/env python3
"""Seed coverage_map.yaml from the repository taxonomy and rules."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Set, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract_review_app.analysis.labels_taxonomy import LABELS_CANON  # noqa: E402
from contract_review_app.legal_rules import loader  # noqa: E402
from contract_review_app.legal_rules.coverage_map import (  # noqa: E402
    COVERAGE_MAP_PATH,
    _normalize_label,
)
from contract_review_app.legal_rules.coverage_zones import (  # noqa: E402
    HIGH_IMPORTANCE_ZONES,
    SERVICE_LABEL_IDS,
    ZONE_LABEL_ALLOWLIST,
    ZONE_LABEL_BLACKLIST,
    ZONE_RULE_BLACKLIST,
    ZONE_SEED_DATA,
)


def _tokenize(value: str | None) -> Set[str]:
    if not value:
        return set()
    normalized = _normalize_label(value)
    if not normalized:
        return set()
    tokens = {normalized}
    separators = [" ", "-", "/", "\\", ".", ":", ";"]
    interim = normalized
    for sep in separators:
        interim = interim.replace(sep, " ")
    for part in interim.split():
        part = part.strip()
        if part:
            tokens.add(part)
    return {token for token in tokens if token}


def _build_label_catalog() -> Dict[str, Set[str]]:
    catalog: Dict[str, Set[str]] = {}
    for label_id, meta in LABELS_CANON.items():
        tokens = _tokenize(label_id)
        for synonym in meta.get("high_priority_synonyms", []) or []:
            tokens.update(_tokenize(synonym))
        catalog[label_id] = tokens
    return catalog


def _match_labels(
    zone_id: str,
    hints: Sequence[str],
    catalog: Mapping[str, Set[str]],
) -> Tuple[Set[str], Set[str]]:
    matched: Set[str] = set()
    missing: Set[str] = set()
    for hint in hints:
        normalized = _normalize_label(hint)
        if not normalized:
            continue
        local_matches = {
            label_id
            for label_id, tokens in catalog.items()
            if normalized == _normalize_label(label_id) or normalized in tokens
        }
        if not local_matches:
            missing.add(hint)
            continue
        matched.update(local_matches)
    allowlist = ZONE_LABEL_ALLOWLIST.get(zone_id)
    if allowlist:
        matched.update(allowlist)
    blacklist = ZONE_LABEL_BLACKLIST.get(zone_id)
    if blacklist:
        matched.difference_update(blacklist)
    return matched, missing


def _build_rule_tokens(rules: Sequence[Mapping[str, object]]) -> Dict[str, Set[str]]:
    rule_tokens: Dict[str, Set[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("id") or rule.get("rule_id") or "").strip()
        if not rule_id:
            continue
        tokens: Set[str] = set()
        fields: Iterable[object] = (
            rule.get("title"),
            rule.get("clause_type"),
            rule.get("pack"),
        )
        for field in fields:
            if isinstance(field, str):
                tokens.update(_tokenize(field))
        requires_clause = rule.get("requires_clause") or []
        for clause in requires_clause if isinstance(requires_clause, Iterable) else []:
            if isinstance(clause, str):
                tokens.update(_tokenize(clause))
        doc_types = rule.get("doc_types") or []
        for doc_type in doc_types if isinstance(doc_types, Iterable) else []:
            if isinstance(doc_type, str):
                tokens.update(_tokenize(doc_type))
        rule_tokens[rule_id] = {token for token in tokens if token}
    return rule_tokens


def _match_rules(
    zone_id: str,
    hints: Sequence[str],
    rule_tokens: Mapping[str, Set[str]],
) -> Tuple[Set[str], Set[str]]:
    normalized_hints = [
        _normalize_label(hint) for hint in hints if _normalize_label(hint)
    ]
    matched: Set[str] = set()
    empty_hints: Set[str] = set()
    if not normalized_hints:
        empty_hints.update(hints)
    for rule_id, tokens in rule_tokens.items():
        for hint in normalized_hints:
            if hint in tokens or any(
                hint in token or token in hint for token in tokens
            ):
                matched.add(rule_id)
                break
    blacklist = ZONE_RULE_BLACKLIST.get(zone_id)
    if blacklist:
        matched.difference_update(blacklist)
    return matched, empty_hints


def _coerce_bool_map(values: Mapping[str, object]) -> Dict[str, bool]:
    return {key: bool(values.get(key, False)) for key in sorted(values)}


def build_seed() -> Tuple[Dict[str, object], Dict[str, object]]:
    label_catalog = _build_label_catalog()
    rules = loader.load_rules()
    rule_tokens = _build_rule_tokens(rules)
    rule_lookup = {str(rule.get("id") or rule.get("rule_id")): rule for rule in rules}

    zones_payload = []
    used_labels: Set[str] = set()
    covered_rules: Set[str] = set()
    missing_labels_report: Dict[str, Set[str]] = defaultdict(set)
    missing_rule_hints: Dict[str, Set[str]] = defaultdict(set)

    for seed in ZONE_SEED_DATA:
        labels_matched, missing = _match_labels(
            seed.zone_id, seed.label_hints, label_catalog
        )
        if missing:
            missing_labels_report[seed.zone_id].update(missing)
        rules_matched, empty = _match_rules(seed.zone_id, seed.rule_hints, rule_tokens)
        if empty:
            missing_rule_hints[seed.zone_id].update(empty)

        labels_sorted = sorted(labels_matched)
        rules_sorted = sorted(rules_matched)

        used_labels.update(labels_sorted)
        covered_rules.update(rules_sorted)

        zone_payload = {
            "zone_id": seed.zone_id,
            "zone_name": seed.zone_name,
            "description": seed.description,
            "label_selectors": {
                "any": labels_sorted,
                "all": [],
                "none": [],
            },
            "entity_selectors": _coerce_bool_map(seed.entity_selectors),
            "rule_ids_opt": rules_sorted,
            "weight": seed.weight,
            "required": bool(seed.required),
        }
        zones_payload.append(zone_payload)

    taxonomy_labels = set(LABELS_CANON.keys()) - set(SERVICE_LABEL_IDS)
    unused_labels = sorted(taxonomy_labels.difference(used_labels))

    metrics = {
        "zones_total": len(zones_payload),
        "labels_used": len(used_labels),
        "labels_total": len(taxonomy_labels),
        "rules_covered": len(covered_rules),
        "rules_total": len(rule_lookup),
        "missing_labels": {k: sorted(v) for k, v in missing_labels_report.items() if v},
        "missing_rule_hints": {
            k: sorted(v) for k, v in missing_rule_hints.items() if v
        },
        "unused_labels": unused_labels,
        "high_importance_zones": sorted(HIGH_IMPORTANCE_ZONES),
    }

    payload = {"version": 1, "zones": zones_payload}
    return payload, metrics


def write_yaml(payload: Mapping[str, object], *, dry_run: bool = False) -> None:
    if dry_run:
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        return
    COVERAGE_MAP_PATH.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def print_report(metrics: Mapping[str, object]) -> None:
    zones_total = metrics.get("zones_total", 0)
    labels_used = metrics.get("labels_used", 0)
    labels_total = metrics.get("labels_total", 1)
    rules_covered = metrics.get("rules_covered", 0)
    rules_total = metrics.get("rules_total", 1)
    label_ratio = labels_used / labels_total if labels_total else 0.0
    rule_ratio = rules_covered / rules_total if rules_total else 0.0

    summary = {
        "zones_total": zones_total,
        "labels_used": labels_used,
        "labels_total": labels_total,
        "labels_ratio": round(label_ratio, 4),
        "rules_covered": rules_covered,
        "rules_total": rules_total,
        "rules_ratio": round(rule_ratio, 4),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    missing_labels = metrics.get("missing_labels") or {}
    if missing_labels:
        print("\n[warn] Unmatched label hints:")
        for zone_id, hints in sorted(missing_labels.items()):
            print(f"  - {zone_id}: {', '.join(hints)}")

    missing_rule_hints = metrics.get("missing_rule_hints") or {}
    if missing_rule_hints:
        print("\n[warn] Rule hints without tokens:")
        for zone_id, hints in sorted(missing_rule_hints.items()):
            print(f"  - {zone_id}: {', '.join(hints)}")

    unused_labels = metrics.get("unused_labels") or []
    if unused_labels:
        print("\n[info] Top unused labels:")
        for label in unused_labels[:10]:
            print(f"  - {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print YAML to stdout instead of writing"
    )
    args = parser.parse_args()

    payload, metrics = build_seed()
    write_yaml(payload, dry_run=args.dry_run)
    print_report(metrics)


if __name__ == "__main__":
    main()
