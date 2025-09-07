$ErrorActionPreference="Stop"
# Убедиться в dev-зависимостях
python - << 'PY'
import importlib, sys
for m in ["httpx", "respx", "pytest"]:
    importlib.import_module(m)
print("Deps OK")
PY

$env:FEATURE_INTEGRATIONS="1"
$env:FEATURE_COMPANIES_HOUSE="1"
# Не подставлять реальный ключ в тестах: клиент мокируется

$py=".\.venv\Scripts\pytest"
& $py -q tests\integrations\test_ch_client.py;          if ($LASTEXITCODE -ne 0) { exit 1 }
& $py -q tests\api\test_companies_endpoints.py;         if ($LASTEXITCODE -ne 0) { exit 1 }
& $py -q tests\integrations\test_enrich_parties.py;     if ($LASTEXITCODE -ne 0) { exit 1 }
& $py -q tests\panel\test_analyze_enrichment_pipeline.py; if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "OK: Block 7 ALL GREEN"
