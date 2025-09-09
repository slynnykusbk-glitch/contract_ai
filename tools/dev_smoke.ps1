param([int]$TimeoutSec=40)
$ErrorActionPreference="SilentlyContinue"

# wait server
$deadline = (Get-Date).AddSeconds($TimeoutSec)
do {
  $h = curl.exe -sk https://localhost:9443/health
  if ($LASTEXITCODE -eq 0 -and ($h -match '"ok"' -or $h -match '"status"\s*:\s*"ok"')) { break }
  Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

if (-not $h) { Write-Error "Health check failed"; exit 1 }
Write-Host "OK /health: $h"

# analyze
$SCHEMA="1.4"
$BODY='{"text":"Hello","language":"en"}'
$r = curl.exe -sk --http1.1 -H "Content-Type: application/json" -H "x-api-key: local-test-key-123" -H "x-schema-version: 1.4" -X POST --data $BODY https://localhost:9443/api/analyze
if ($LASTEXITCODE -ne 0 -or ($r -notmatch '"status"\s*:\s*"ok"')) { Write-Error "/api/analyze failed: $r"; exit 2 }
Write-Host "OK /api/analyze"

# gpt-draft
$BODY2='{"text":"Please rephrase","language":"en"}'
$r2 = curl.exe -sk --http1.1 -H "Content-Type: application/json" -H "x-api-key: local-test-key-123" -H "x-schema-version: 1.4" -X POST --data $BODY2 https://localhost:9443/api/gpt-draft
if ($LASTEXITCODE -ne 0 -or ($r2 -notmatch '"status"\s*:\s*"ok"')) { Write-Error "/api/gpt-draft failed: $r2"; exit 3 }
Write-Host "OK /api/gpt-draft"

# qa-recheck (минимум)
$BODY3='{"text":"hello","rules":{}}'
$r3 = curl.exe -sk --http1.1 -H "Content-Type: application/json" -H "x-api-key: local-test-key-123" -H "x-schema-version: 1.4" -X POST --data $BODY3 https://localhost:9443/api/qa-recheck
if ($LASTEXITCODE -ne 0 -or ($r3 -notmatch '"status"\s*:\s*"ok"')) { Write-Error "/api/qa-recheck failed: $r3"; exit 4 }
Write-Host "OK /api/qa-recheck"

Write-Host "Smoke OK"
