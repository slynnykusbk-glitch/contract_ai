from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Sequence

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)

FIXTURES = {
    "services_combo": [Path("fixtures/contracts/mixed_sample.txt")],
    "supply_combo": [
        Path("fixtures/contracts/mixed_sample.txt"),
        Path("fixtures/soft_no_goods_ins.txt"),
        Path("fixtures/soft_no_flowdown.txt"),
    ],
    "compliance_combo": [
        Path("fixtures/contracts/mixed_sample.txt"),
        Path("fixtures/soft_mixed_warns.txt"),
        Path("fixtures/soft_low_cgl.txt"),
    ],
}


def _load_text(paths: Sequence[Path]) -> str:
    return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_coverage_summary_useful():
    client, modules = _build_client("1")
    try:
        for name, paths in FIXTURES.items():
            text = _load_text(paths)
            response = client.post(
                "/api/analyze", headers=_headers(), json={"text": text}
            )
            assert response.status_code == 200, name
            cid = response.headers.get("x-cid")
            assert cid, name
            trace_response = client.get(f"/api/trace/{cid}")
            assert trace_response.status_code == 200, name
            trace_body = trace_response.json()
            coverage = trace_body.get("coverage")
            assert isinstance(coverage, dict), name

            zones_total = int(coverage.get("zones_total", 0))
            assert zones_total >= 30, name
            zones_present = int(coverage.get("zones_present", 0))
            assert zones_present >= max(1, ceil(zones_total * 0.25)), name

            zones_candidates = int(coverage.get("zones_candidates", 0))
            zones_fired = int(coverage.get("zones_fired", 0))
            assert (zones_candidates + zones_fired) >= 8, name

            details = coverage.get("details") or []
            assert details, name
            for detail in details:
                matched = detail.get("matched_labels") or []
                candidate_rules = detail.get("candidate_rules") or []
                fired_rules = detail.get("fired_rules") or []
                missing_rules = detail.get("missing_rules") or []
                assert (
                    matched or candidate_rules or fired_rules or missing_rules
                ), f"zone {detail.get('zone_id')} has no signals"
    finally:
        _cleanup(client, modules)
