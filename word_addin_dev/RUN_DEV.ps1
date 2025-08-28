#requires -version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

# Шляхи незалежно від того, звідки запускаєш
$root = Split-Path -Parent $PSCommandPath           # ...\word_addin_dev
$repo = Split-Path -Parent $root                    # ...\contract_ai
$mf   = Join-Path $root "manifest.xml"
$cert = Join-Path $root "certs\localhost.pem"
$key  = Join-Path $root "certs\localhost-key.pem"

Write-Host "Kill Word + clear caches..." -ForegroundColor Cyan
taskkill /IM WINWORD.EXE /F 2>$null | Out-Null
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*" -Recurse -Force -EA SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*" -Recurse -Force -EA SilentlyContinue

Write-Host "Force localhost in manifest..." -ForegroundColor Cyan
(Get-Content $mf -Raw) -replace '127\.0\.0\.1','localhost' | Set-Content $mf -Encoding UTF8 -NoNewline

Write-Host "Trust dev certificate (user + machine if можна)..." -ForegroundColor Cyan
Import-Certificate -FilePath $cert -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
try { Import-Certificate -FilePath $cert -CertStoreLocation Cert:\LocalMachine\Root | Out-Null } catch {}

Write-Host "Ensure Trusted Catalog \\localhost\wef (HKCU)..." -ForegroundColor Cyan
$catKey = 'HKCU:\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\8f6f3c9e-8a7c-4d3e-9f6a-000000000001'
New-Item -Path $catKey -Force | Out-Null
New-ItemProperty -Path $catKey -Name Id         -Value '8f6f3c9e-8a7c-4d3e-9f6a-000000000001' -PropertyType String -Force | Out-Null
New-ItemProperty -Path $catKey -Name Url        -Value '\\localhost\wef'                   -PropertyType String -Force | Out-Null
New-ItemProperty -Path $catKey -Name ShowInMenu -Value 1                                   -PropertyType DWord  -Force | Out-Null
New-ItemProperty -Path $catKey -Name Type       -Value 2                                   -PropertyType DWord  -Force | Out-Null

# Спроба створити SMB-шару (якщо є права). Якщо ні — просто пропустимо.
try {
  $me = "$env:COMPUTERNAME\$env:USERNAME"
  if (-not (Get-SmbShare -Name wef -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name wef -Path $root -FullAccess $me -CachingMode None | Out-Null
  } else {
    Set-SmbShare -Name wef -Path $root -Force | Out-Null
  }
} catch { }

# Python
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python | Select-Object -First 1 -ExpandProperty Source) }

$env:AI_PROVIDER = "mock"

Write-Host "Start backend on https://localhost:9443 ..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized -WorkingDirectory $repo -FilePath $py -ArgumentList @(
  "-m","uvicorn","contract_review_app.api.app:app",
  "--host","localhost","--port","9443",
  "--ssl-certfile", $cert,
  "--ssl-keyfile" , $key,
  "--reload"
)

Write-Host "Start panel server on https://localhost:3000 ..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized -WorkingDirectory $repo -FilePath $py -ArgumentList @(
  "word_addin_dev\serve_https_panel.py","--host","localhost"
)

Start-Sleep -Seconds 1
Write-Host "Open Word..." -ForegroundColor Cyan
Start-Process winword.exe

Write-Host "`nГотово. У Word: Вставка → Мои надстройки → вкладка 'Общая папка' → 'Contract AI — Draft Assistant (Dev)'." -ForegroundColor Green
Read-Host "Натисни Enter, щоб закрити це вікно"
