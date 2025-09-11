param(
  [string]$Branch
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")  # в корень репо

# 1) Git sync
git fetch origin
if ([string]::IsNullOrWhiteSpace($Branch)) {
  $Branch = (git rev-parse --abbrev-ref HEAD).Trim()
}
git switch $Branch
git pull

# 2) Сборка панели
New-Item -ItemType Directory -Force -Path .\contract_review_app\panel | Out-Null
Push-Location .\word_addin_dev\app
npm ci
npx esbuild .\assets\taskpane.ts --bundle --platform=browser --target=es2019 --sourcemap=external `
  --outfile=..\..\contract_review_app\panel\taskpane.bundle.js
Pop-Location

# 3) Показать, что собралось
Get-Item .\contract_review_app\panel\taskpane.bundle.js | fl FullName,Length,LastWriteTime

# 4) Окружение (ключи не трогаем: читаем из локального файла, которого нет в git)
$env:SCHEMA_VERSION = "1.4"
$env:PROVIDER       = "azure"
$env:X_API_KEY      = $(Get-Content -Raw -ErrorAction SilentlyContinue .\var\local_api_key.txt)
if ([string]::IsNullOrWhiteSpace($env:X_API_KEY)) {
  Write-Warning "X_API_KEY не найден (var\local_api_key.txt). Использую dev-ключ."
  $env:X_API_KEY = "local-test-key-123"
}

# 5) Старт uvicorn c TLS
$cert = ".\var\localhost.crt"
$key  = ".\var\localhost.key"
if (!(Test-Path $cert) -or !(Test-Path $key)) {
  throw "Нет сертификата/ключа для https: $cert / $key"
}

Write-Host "LLM_PROVIDER=$env:PROVIDER  KEYLEN=$($env:X_API_KEY.Length)"
python -m uvicorn contract_review_app.api.app:app `
  --reload `
  --ssl-keyfile  $key `
  --ssl-certfile $cert `
  --host 127.0.0.1 --port 9443
