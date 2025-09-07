from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_metrics(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True)
    p.add_argument("--current", required=True)
    args = p.parse_args(argv)

    baseline = load_metrics(Path(args.baseline))
    current = load_metrics(Path(args.current))
    m = current.get("metrics", {})
    rules = m.get("rules", [])
    if rules:
        f1 = sum(r.get("f1", 0.0) for r in rules) / len(rules)
    else:
        f1 = 0.0
    coverage = m.get("coverage", {}).get("coverage", 0.0)
    acceptance = m.get("acceptance", {}).get("acceptance_rate", 0.0)
    perf = m.get("perf", {}).get("avg_ms_per_page", 0.0)

    if f1 < baseline.get("f1_min", 0.0):
        return 1
    if coverage < baseline.get("coverage_min", 0.0):
        return 1
    if acceptance < baseline.get("acceptance_min", 0.0):
        return 1
    if perf > baseline.get("perf_max_ms_page", float("inf")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
