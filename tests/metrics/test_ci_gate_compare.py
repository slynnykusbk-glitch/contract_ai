from __future__ import annotations

import json
import subprocess
from pathlib import Path

from contract_review_app.api.models import SCHEMA_VERSION


def test_ci_gate_compare(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "f1_min": 0.9,
                "coverage_min": 0.8,
                "acceptance_min": 0.9,
                "perf_max_ms_page": 10.0,
            }
        ),
        encoding="utf-8",
    )
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "snapshot_at": "2020-01-01T00:00:00Z",
                "metrics": {
                    "rules": [
                        {
                            "rule_id": "r1",
                            "tp": 0,
                            "fp": 0,
                            "fn": 1,
                            "precision": 0.0,
                            "recall": 0.0,
                            "f1": 0.0,
                        }
                    ],
                    "coverage": {"rules_total": 1, "rules_fired": 0, "coverage": 0.0},
                    "acceptance": {"applied": 0, "rejected": 1, "acceptance_rate": 0.0},
                    "perf": {"docs": 1, "avg_ms_per_page": 20.0},
                },
            }
        ),
        encoding="utf-8",
    )
    rc = subprocess.run(
        [
            "python",
            "tools/metrics_compare.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
        ],
        cwd=Path(__file__).resolve().parents[2],
    ).returncode
    assert rc == 1
