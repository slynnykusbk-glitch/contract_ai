import textwrap
from pathlib import Path

import pytest

from contract_review_app.legal_rules import coverage_map


@pytest.fixture(autouse=True)
def reset_cache():
    coverage_map.invalidate_cache()
    yield
    coverage_map.invalidate_cache()


def _write_map(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "coverage_map.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_valid_map_v1_ok(tmp_path, monkeypatch):
    path = _write_map(
        tmp_path,
        """
        version: 1
        zones:
          - zone_id: payment
            zone_name: Payment
            label_selectors:
              any: [payment]
              all: []
              none: []
        """,
    )
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", path)
    cmap = coverage_map.load_coverage_map()
    assert cmap is not None
    assert cmap.version == 1
    assert len(cmap.zones) == 1
    assert "payment" in cmap.label_index


def test_duplicate_zone_id_fails(tmp_path, monkeypatch):
    path = _write_map(
        tmp_path,
        """
        version: 1
        zones:
          - zone_id: payment
            zone_name: Payment
            label_selectors:
              any: [payment]
              all: []
              none: []
          - zone_id: payment
            zone_name: Duplicate
            label_selectors:
              any: [payment]
              all: []
              none: []
        """,
    )
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", path)
    assert coverage_map.load_coverage_map() is None


def test_bad_entity_selector_key_fails(tmp_path, monkeypatch):
    path = _write_map(
        tmp_path,
        """
        version: 1
        zones:
          - zone_id: payment
            zone_name: Payment
            label_selectors:
              any: [payment]
              all: []
              none: []
            entity_selectors:
              amounts: true
              foo: true
        """,
    )
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", path)
    assert coverage_map.load_coverage_map() is None


def test_version_required_and_ge_1(tmp_path, monkeypatch):
    path = _write_map(
        tmp_path,
        """
        version: 0
        zones:
          - zone_id: payment
            zone_name: Payment
            label_selectors:
              any: [payment]
              all: []
              none: []
        """,
    )
    monkeypatch.setattr(coverage_map, "COVERAGE_MAP_PATH", path)
    assert coverage_map.load_coverage_map() is None
