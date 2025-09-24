#!/usr/bin/env bash
set -euo pipefail

export FEATURE_TRACE_ARTIFACTS=1
export FEATURE_REASON_OFFSETS=1
export FEATURE_COVERAGE_MAP=1
export FEATURE_AGENDA_SORT=1
export FEATURE_AGENDA_STRICT_MERGE=0

echo "[run_api_with_flags] Flags:"
env | grep -E '^FEATURE_' || true

python -m contract_review_app.api.app
