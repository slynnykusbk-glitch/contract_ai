#!/usr/bin/env python3
"""Validate the coverage map specification."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_app.legal_rules import coverage_map


def run(strict: bool = False) -> int:
    coverage_map.invalidate_cache()
    cmap = coverage_map.load_coverage_map()
    if cmap is None:
        print("Failed to load coverage map", file=sys.stderr)
        return 1

    zones_total = len(cmap.zones)
    if strict or os.getenv("FEATURE_COVERAGE_LINT_STRICT") == "1":
        if zones_total < 30:
            print("Coverage map must contain at least 30 zones", file=sys.stderr)
            return 1

    summary = {
        "version": cmap.version,
        "zones_total": zones_total,
        "labels_indexed": len(cmap.label_index),
        "rules_indexed": len(cmap.rule_index),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate coverage map")
    parser.add_argument("--strict", action="store_true", help="Enforce strict checks")
    args = parser.parse_args()
    raise SystemExit(run(strict=args.strict))


if __name__ == "__main__":
    main()
