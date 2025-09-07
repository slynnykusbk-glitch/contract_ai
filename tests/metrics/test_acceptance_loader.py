from __future__ import annotations

import json
from pathlib import Path

from contract_review_app.metrics.compute import load_acceptance


def test_acceptance_loader(tmp_path: Path):
    lines = [
        {"action": "applied"},
        {"action": "rejected"},
        {"action": "applied"},
    ]
    p = tmp_path / "replay_buffer.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj) + "\n")
    acc = load_acceptance(p)
    assert acc.applied == 2
    assert acc.rejected == 1
    assert abs(acc.acceptance_rate - 0.6) < 1e-9
