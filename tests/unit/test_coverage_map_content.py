from __future__ import annotations

from contract_review_app.analysis.labels_taxonomy import LABELS_CANON
from contract_review_app.legal_rules import coverage_map, loader
from contract_review_app.legal_rules.coverage_zones import (
    HIGH_IMPORTANCE_ZONES,
    ZONE_ENTITY_MATRIX,
)


def _load_map():
    coverage_map.invalidate_cache()
    cmap = coverage_map.load_coverage_map()
    assert cmap is not None, "coverage map failed to load"
    return cmap


def test_high_importance_zones_have_labels_and_entities():
    cmap = _load_map()
    zone_lookup = {zone.zone_id: zone for zone in cmap.zones}
    for zone_id in HIGH_IMPORTANCE_ZONES:
        assert zone_id in zone_lookup, f"zone '{zone_id}' missing from map"
        zone = zone_lookup[zone_id]
        assert (
            len(zone.label_any) >= 5
        ), f"zone '{zone_id}' must have >=5 label selectors"
        expected_entities = ZONE_ENTITY_MATRIX.get(zone_id)
        if expected_entities is not None:
            current = {
                key: bool(zone.entity_selectors.get(key, False))
                for key in expected_entities
            }
            expected = {key: bool(value) for key, value in expected_entities.items()}
            assert (
                current == expected
            ), f"zone '{zone_id}' entity selectors mismatch: {current} != {expected}"


def test_zone_labels_exist_in_taxonomy():
    cmap = _load_map()
    taxonomy_labels = set(LABELS_CANON.keys())
    alias_whitelist = {
        alias for aliases in coverage_map.ZONE_ALIASES.values() for alias in aliases
    }
    for zone in cmap.zones:
        selectors = zone.label_any.union(zone.label_all).union(zone.label_none)
        for label in selectors:
            if label in alias_whitelist:
                continue
            assert (
                label in taxonomy_labels
            ), f"label '{label}' from zone '{zone.zone_id}' not in taxonomy"


def test_rule_ids_exist():
    cmap = _load_map()
    rules = loader.load_rules()
    rule_ids = {
        str(rule.get("id") or rule.get("rule_id") or "").strip()
        for rule in rules
        if str(rule.get("id") or rule.get("rule_id") or "").strip()
    }
    for zone in cmap.zones:
        for rule_id in zone.rule_ids:
            assert (
                rule_id in rule_ids
            ), f"zone '{zone.zone_id}' references unknown rule '{rule_id}'"
