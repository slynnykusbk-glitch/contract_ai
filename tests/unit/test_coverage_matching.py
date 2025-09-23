import textwrap
from pathlib import Path

import pytest

from contract_review_app.legal_rules import coverage_map


@pytest.fixture(autouse=True)
def reset_cache():
    coverage_map.invalidate_cache()
    yield
    coverage_map.invalidate_cache()


def _write_map(tmp_path: Path) -> Path:
    content = """
    version: 1
    zones:
      - zone_id: payment
        zone_name: Payment
        label_selectors:
          any: [Payment]
          all: []
          none: []
        entity_selectors:
          amounts: true
          durations: true
        rule_ids_opt: [pay_late_interest_v1]
      - zone_id: notices
        zone_name: Notices
        label_selectors:
          any: [notice]
          all: []
          none: [skip]
    """
    path = tmp_path / "coverage_map.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _base_segment(labels):
    return {
        "labels": labels,
        "entities": {
            "amounts": [1, 2],
            "durations": [{"value": {"days": 10}}],
        },
        "span": [0, 50],
    }


def test_zone_present_when_labels_match(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", _write_map(tmp_path))
    cov = coverage_map.build_coverage(
        segments=[_base_segment(["Payment"])],
        dispatch_candidates_by_segment=[set()],
        triggered_rule_ids=set(),
        rule_lookup={"pay_late_interest_v1": {}},
    )
    assert cov is not None
    detail = {item["zone_id"]: item for item in cov["details"]}["payment"]
    assert detail["status"] == "present"
    assert detail["matched_labels"] == ["payment"]
    assert detail["matched_entities"]["amounts"] == 2
    assert detail["matched_entities"]["durations"] == 1


def test_zone_candidate_when_rules_match(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", _write_map(tmp_path))
    cov = coverage_map.build_coverage(
        segments=[_base_segment(["Payment"])],
        dispatch_candidates_by_segment=[{"pay_late_interest_v1"}],
        triggered_rule_ids=set(),
        rule_lookup={"pay_late_interest_v1": {}},
    )
    detail = {item["zone_id"]: item for item in cov["details"]}["payment"]
    assert detail["status"] == "rules_candidate"
    assert detail["candidate_rules"] == ["pay_late_interest_v1"]


def test_zone_fired_takes_priority(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", _write_map(tmp_path))
    cov = coverage_map.build_coverage(
        segments=[_base_segment(["Payment"])],
        dispatch_candidates_by_segment=[{"pay_late_interest_v1"}],
        triggered_rule_ids={"pay_late_interest_v1"},
        rule_lookup={"pay_late_interest_v1": {}},
    )
    detail = {item["zone_id"]: item for item in cov["details"]}["payment"]
    assert detail["status"] == "rules_fired"
    assert detail["fired_rules"] == ["pay_late_interest_v1"]
    assert detail["candidate_rules"] == ["pay_late_interest_v1"]
    assert detail["missing_rules"] == []


def test_none_selector_keeps_zone_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", _write_map(tmp_path))
    cov = coverage_map.build_coverage(
        segments=[_base_segment(["notice", "skip"])],
        dispatch_candidates_by_segment=[{"notice_rule"}],
        triggered_rule_ids=set(),
        rule_lookup={"notice_rule": {}},
    )
    assert cov is not None
    zone_ids = {item["zone_id"] for item in cov["details"]}
    assert "notices" not in zone_ids
