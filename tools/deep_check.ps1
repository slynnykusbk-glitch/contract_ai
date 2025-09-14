#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Section($title) { Write-Host "=== $title ===" -ForegroundColor Cyan }

Section "Git status"
git rev-parse --abbrev-ref HEAD
git status --porcelain

Section "Merge markers"
git grep -n "<<<<<<<\|=======\|>>>>>>>" | Out-Host
if ($LASTEXITCODE -eq 0) { Write-Host "[FAIL] merge markers found" -ForegroundColor Red } else { Write-Host "[OK] no merge markers" -ForegroundColor Green }

Section "Legacy imports / API use"
git grep -n "from `"./safe-search\.ts`"" | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "[OK] no safe-search imports" -ForegroundColor Green }
git grep -n "body\.search\(" | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "[OK] no raw body.search" -ForegroundColor Green }
git grep -n "safeBodySearch\(.*\)\.load" | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "[OK] no .load after safeBodySearch" -ForegroundColor Green }
git grep -n "load('items')" -- word_addin_dev/app/assets/taskpane.ts contract_review_app/contract_review_app/static/panel/app/assets/taskpane.ts | Out-Host

Section "Env"
$keys = "LLM_PROVIDER","AZURE_OPENAI_ENDPOINT","AZURE_OPENAI_API_VERSION","AZURE_OPENAI_DEPLOYMENT","AZURE_OPENAI_API_KEY","SCHEMA_VERSION"
foreach ($k in $keys) {
  if ($k -eq "AZURE_OPENAI_API_KEY") {
    Write-Host "$k=$($env:AZURE_OPENAI_API_KEY.Length)"
  } else {
    Write-Host "$k=$($env:$k)"
  }
}
try {
  $aoaiHost = ([uri]$env:AZURE_OPENAI_ENDPOINT).Host
  Write-Host "AOAI host: $aoaiHost"
  Resolve-DnsName $aoaiHost | Out-Host
  Test-NetConnection $aoaiHost -Port 443 | Select-Object ComputerName,RemoteAddress,TcpTestSucceeded | Out-Host
} catch { Write-Host "[WARN] AOAI endpoint not set or invalid" -ForegroundColor Yellow }

Section "Local API"
& $env:ComSpec /c "curl.exe -k https://127.0.0.1:9443/health"
& $env:ComSpec /c "curl.exe -k -sS -H ""content-type: application/json"" -d ""{\""cid\"":\""doctor\"",\""clause\"":\""ping\""}"" https://127.0.0.1:9443/api/gpt-draft"

Section "Build"
npm --prefix word_addin_dev ci
npm --prefix word_addin_dev run build

Section "Pre-commit"
pre-commit --version
pre-commit run --all-files

Section "Summary"
Write-Host "All checks finished." -ForegroundColor Green
