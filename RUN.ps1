# Contract AI - one click run (ASCII-safe)

$ErrorActionPreference = "Stop"

# Paths
$root  = "C:\Users\Ludmila\contract_ai"
$front = Join-Path $root "word_addin_dev"
$man   = Join-Path $front "manifest.xml"
$py    = Join-Path $root ".venv\Scripts\python.exe"
$localLabel = 'local' + 'host'
$certFolder = Join-Path $env:USERPROFILE '.office-addin-dev-certs'
$certFile = ('{0}.crt' -f $localLabel)
$keyFile = ('{0}.key' -f $localLabel)
$cert  = Join-Path $certFolder $certFile
$key   = Join-Path $certFolder $keyFile

# NPM global bin (to call http-server and office-addin-dev-settings directly)
$npmBin = Join-Path $env:APPDATA "npm"
$httpExe  = Join-Path $npmBin "http-server.cmd"
$addinExe = Join-Path $npmBin "office-addin-dev-settings.cmd"

# Basic checks
if (-not (Test-Path $root))  { throw "Folder missing: $root" }
if (-not (Test-Path $front)) { throw "Folder missing: $front" }
if (-not (Test-Path $man))   { throw "Manifest missing: $man" }
if (-not (Test-Path $py))    { throw "Venv Python missing: $py" }
if (-not (Test-Path $cert))  { throw "Cert missing: $cert (run: npx office-addin-dev-certs install)" }
if (-not (Test-Path $key))   { throw "Key missing:  $key (run: npx office-addin-dev-certs install)" }
if (-not (Test-Path $httpExe))  { throw "http-server not found. Run: npm i -g http-server" }
if (-not (Test-Path $addinExe)) { throw "office-addin-dev-settings not found. Run: npm i -g office-addin-dev-settings" }

Write-Host "[OK] Checks passed." -ForegroundColor Green

# Clean start (close Word/WebView2) — safe if processes not running
$prevPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process msedgewebview2 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$ErrorActionPreference = $prevPref

# Start BACKEND (https://127.0.0.1:9000) in a new PowerShell window
$backendCmd = "cd `"$root`"; `"$py`" -m uvicorn contract_review_app.api.app:app --host :: --port 9000 --ssl-certfile `"$cert`" --ssl-keyfile `"$key`" --reload --log-level debug"
Start-Process "powershell.exe" -ArgumentList "-NoExit","-Command",$backendCmd | Out-Null

Start-Sleep -Seconds 2

# Start FRONT (https://127.0.0.1:3000) in a new PowerShell window
$frontCmd = "cd `"$front`"; `"$httpExe`" . -S -C `"$cert`" -K `"$key`" -p 3000 -a 127.0.0.1"
Start-Process "powershell.exe" -ArgumentList "-NoExit","-Command",$frontCmd | Out-Null

Start-Sleep -Seconds 2

# Sideload into Word
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef" -Recurse -Force -ErrorAction SilentlyContinue
& $addinExe unregister "$man" 2>$null
& $addinExe register   "$man"
& $addinExe webview    "$man" edge
& $addinExe sideload   "$man" --app Word

Write-Host ""
Write-Host "[READY] Backend: https://127.0.0.1:9000   Front: https://127.0.0.1:3000" -ForegroundColor Green
Write-Host "If panel cannot reach backend, set Backend to https://127.0.0.1:9000" -ForegroundColor Yellow
