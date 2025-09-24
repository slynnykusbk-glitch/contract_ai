$ErrorActionPreference = "Stop"

# === Feature flags ===
$env:FEATURE_TRACE_ARTIFACTS = "1"
$env:FEATURE_REASON_OFFSETS  = "1"
$env:FEATURE_COVERAGE_MAP    = "1"
$env:FEATURE_AGENDA_SORT     = "1"
$env:FEATURE_AGENDA_STRICT_MERGE = "0"

Write-Host "[run_api_with_flags] Flags:"
Write-Host " FEATURE_TRACE_ARTIFACTS=$($env:FEATURE_TRACE_ARTIFACTS)"
Write-Host " FEATURE_REASON_OFFSETS=$($env:FEATURE_REASON_OFFSETS)"
Write-Host " FEATURE_COVERAGE_MAP=$($env:FEATURE_COVERAGE_MAP)"
Write-Host " FEATURE_AGENDA_SORT=$($env:FEATURE_AGENDA_SORT)"
Write-Host " FEATURE_AGENDA_STRICT_MERGE=$($env:FEATURE_AGENDA_STRICT_MERGE)"

# === Backend launch ===
# Используем стандартный вход в приложение (он уже обслуживает /panel/ и /api/*).
python -m contract_review_app.api.app
