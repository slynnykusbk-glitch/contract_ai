```powershell
# word_addin_dev/RUN_DEV.ps1
Param(
  [switch]$OpenTaskpane
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Write-Info([string]$msg){ Write-Host "[INFO ] $msg" -ForegroundColor Cyan }
function Write-Warn([string]$msg){ Write-Host "[WARN ] $msg" -ForegroundColor Yellow }
function Write-Err ([string]$msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Poll a TCP port until open or timeout (seconds). Returns $true/$false.
function Wait-Port([string]$h, [int]$p, [int]$sec){
  $deadline = (Get-Date).AddSeconds($sec)
  while((Get-Date) -lt $deadline){
    try{
      $client = New-Object System.Net.Sockets.TcpClient
      $iar = $client.BeginConnect($h, $p, $null, $null)
      if($iar.AsyncWaitHandle.WaitOne(250)){
        $client.EndConnect($iar) | Out-Null
        $client.Close()
        return $true
      }
      $client.Close()
    } catch { Start-Sleep -Milliseconds 250 }
  }
  return $false
}

# Gracefully stop potentially conflicting processes
function Kill-Prev{
  Write-Info "Stopping previous Word / WebView / Python processes (if any)..."
  $names = @("WINWORD","msedgewebview2","python","python3","uvicorn")
  foreach($n in $names){
    try{
      Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -ErrorAction SilentlyContinue } catch {}
      }
    } catch {}
  }
  Start-Sleep -Seconds 1
  foreach($n in $names){
    try{
      Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
      }
    } catch {}
  }
}

# Clean Office Web Add-ins caches (best-effort)
function Clean-WEF{
  Write-Info "Cleaning Office Web Add-ins caches..."
  $paths = @(
    Join-Path $env:LOCALAPPDATA "Microsoft\Office\16.0\Wef",
    Join-Path $env:LOCALAPPDATA "Microsoft\Office\16.0\WebServiceCache",
    Join-Path $env:LOCALAPPDATA "Microsoft\EdgeWebView"
  )
  foreach($p in $paths){
    try{
      if(Test-Path $p){
        # Ensure WebView is not locking files
        Get-Process -Name "msedgewebview2" -ErrorAction SilentlyContinue | ForEach-Object {
          try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
      }
    } catch {
      Write-Warn "Could not clean: $p"
    }
  }
}

function Start-Backend {
  param(
    [string]$CertPath,
    [string]$KeyPath
  )
  Write-Info "Starting TLS backend on https://127.0.0.1:9443 ..."
  $args = @(
    "contract_review_app.api.app:app",
    "--host","127.0.0.1",
    "--port","9443",
    "--ssl-certfile",$CertPath,
    "--ssl-keyfile",$KeyPath
  )
  try{
    $proc = Start-Process -FilePath "uvicorn" -ArgumentList $args -PassThru -WindowStyle Normal
    return $proc
  } catch {
    Write-Err "Failed to start uvicorn. Ensure venv is activated and uvicorn installed."
    return $null
  }
}

function Start-Panel {
  param(
    [string]$CertPath,
    [string]$KeyPath
  )
  Write-Info "Starting HTTPS panel on https://127.0.0.1:3000 ..."
  $args = @(
    ".\word_addin_dev\serve_https_panel.py",
    "--cert",$CertPath,
    "--key",$KeyPath
  )
  try{
    $proc = Start-Process -FilePath "python" -ArgumentList $args -PassThru -WindowStyle Normal
    return $proc
  } catch {
    Write-Err "Failed to start HTTPS panel server."
    return $null
  }
}

function Register-Manifest {
  param([string]$ManifestPath)
  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if(-not $npx){
    Write-Warn "Node.js / npx not found. Skipping manifest (un)register steps."
    return
  }
  Write-Info "Registering Office Add-in manifest..."
  try{
    & npx office-addin-dev-settings unregister $ManifestPath 2>$null | Out-Null
  } catch { Write-Warn "Unregister returned non-zero (ignored)." }
  try{
    & npx office-addin-dev-settings register $ManifestPath | Out-Null
  } catch { Write-Warn "Register returned non-zero (ignored)." }
  try{
    & npx office-addin-dev-settings webview $ManifestPath edge | Out-Null
  } catch { Write-Warn "Setting webview engine failed (ignored)." }
}

# ---- Main flow ---------------------------------------------------------------

# Ensure we run from repo root (this script lives in word_addin_dev/)
try { Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")) } catch {}

Kill-Prev

# Activate venv (best-effort)
$venvAct = ".\.venv\Scripts\Activate.ps1"
if(Test-Path $venvAct){
  Write-Info "Activating virtualenv..."
  try { . $venvAct } catch { Write-Warn "Could not activate venv (continuing anyway)." }
} else {
  Write-Warn "No .venv found. Ensure dependencies are installed globally or create a venv."
}

# Generate dev certificates (idempotent)
try{
  if(Test-Path ".\word_addin_dev\gen_dev_certs.py"){
    Write-Info "Ensuring dev certificates exist..."
    python .\word_addin_dev\gen_dev_certs.py 2>$null | Out-Null
  }
} catch { Write-Warn "gen_dev_certs.py failed or missing (continuing)." }

$cert = ".\word_addin_dev\certs\localhost.pem"
$key  = ".\word_addin_dev\certs\localhost-key.pem"

$backendProc = Start-Backend -CertPath $cert -KeyPath $key
if(Wait-Port "127.0.0.1" 9443 30){
  Write-Info "Backend is ready on https://127.0.0.1:9443"
} else {
  Write-Warn "Backend port 9443 not ready within timeout."
}

$panelProc = Start-Panel -CertPath $cert -KeyPath $key
if(Wait-Port "127.0.0.1" 3000 30){
  Write-Info "Panel is ready on https://127.0.0.1:3000"
} else {
  Write-Warn "Panel port 3000 not ready within timeout."
}

Clean-WEF

$manifestPath = (Resolve-Path ".\word_addin_dev\manifest.xml").Path
Register-Manifest -ManifestPath $manifestPath

$ts = [int64](([DateTimeOffset]::UtcNow).ToUnixTimeMilliseconds())
Write-Host ""
Write-Host "PANEL : https://127.0.0.1:3000/taskpane.html?v=$ts"
Write-Host "DOCTOR: https://127.0.0.1:3000/panel_selftest.html?v=$ts"
Write-Host "BACKEND: https://127.0.0.1:9443/health"
Write-Host ""

if($OpenTaskpane){
  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if($npx){
    try{
      & npx office-addin-dev-settings sideload $manifestPath desktop --app word | Out-Null
      Write-Info "Requested Word sideload."
    } catch { Write-Warn "Sideload failed (ignored)." }
  } else {
    Write-Warn "npx not available; skipping sideload."
  }
}

Write-Host "Press Ctrl+C to stop. This window will keep running to host child processes."
try{
  if($backendProc -and $panelProc){
    Wait-Process -Id $backendProc.Id,$panelProc.Id -ErrorAction SilentlyContinue
  } elseif($backendProc){
    Wait-Process -Id $backendProc.Id -ErrorAction SilentlyContinue
  } elseif($panelProc){
    Wait-Process -Id $panelProc.Id -ErrorAction SilentlyContinue
  } else {
    while($true){ Start-Sleep -Seconds 60 }
  }
} catch {}
```

```bat
:: word_addin_dev/START_DEV.bat
@echo off
setlocal
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_DEV.ps1" %*
endlocal

```
