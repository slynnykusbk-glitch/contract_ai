#requires -version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSEdition -eq 'Core') { try { $PSStyle.OutputRendering = 'PlainText' } catch {} }

$repo = Split-Path -Parent $PSScriptRoot

$venvActivate = Join-Path $repo '.venv\Scripts\Activate.ps1'
if (!(Test-Path $venvActivate)) {
    Write-Host 'Creating venv...' -ForegroundColor Cyan
    py -3.11 -m venv (Join-Path $repo '.venv') | Out-Null
}
. $venvActivate

$env:PYTHONPATH = $repo
if (!(Test-Path "$repo\var")) { New-Item -ItemType Directory "$repo\var" | Out-Null }
$env:LEGAL_CORPUS_DSN = "sqlite:///var/corpus.db"
$env:CONTRACTAI_LLM_API = "mock"

$panelPy = Join-Path $repo 'serve_https_panel.py'
$panelRoot = Join-Path $repo 'word_addin_dev'
$panelArgs = @('--host','127.0.0.1','--port','3000','--root',$panelRoot)
$panelArgList = @($panelPy) + $panelArgs
if (-not $panelArgList) { $panelArgList = @('') }
$panelProc = Start-Process "$repo\.venv\Scripts\python.exe" -ArgumentList $panelArgList -WindowStyle Minimized -PassThru

$cert = Join-Path $panelRoot 'certs\panel-cert.pem'
$key  = Join-Path $panelRoot 'certs\panel-key.pem'
$uvArgs = @('-m','uvicorn','contract_review_app.api.app:app',
            '--host','127.0.0.1','--port','9443',
            '--ssl-certfile',$cert,'--ssl-keyfile',$key)
if (-not $uvArgs) { $uvArgs = @('') }
$backendProc = Start-Process "$repo\.venv\Scripts\python.exe" -ArgumentList $uvArgs -WindowStyle Minimized -PassThru

add-type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
  public bool CheckValidationResult(ServicePoint s, X509Certificate c, WebRequest r, int p) { return true; }
}
"@
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy

function Wait-Ok($url) {
  for ($i=0; $i -lt 30; $i++) {
    try { (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2) | Out-Null; return $true } catch { Start-Sleep -Milliseconds 500 }
  }
  return $false
}
$okApi   = Wait-Ok 'https://127.0.0.1:9443/health'
$okPanel = Wait-Ok 'https://127.0.0.1:3000/panel_selftest.html'
if (-not $okApi)   { Write-Host '[ERR] Backend not ready' -ForegroundColor Red }
if (-not $okPanel) { Write-Host '[ERR] Panel not ready'   -ForegroundColor Red }

Start-Process -FilePath 'https://127.0.0.1:3000/panel_selftest.html?v=dev'
Write-Host '[OK] READY. Panel self-test opened.'
Read-Host 'Press Enter to stop services'

foreach ($p in @($backendProc,$panelProc)) {
    try { if (!$p.HasExited) { $p.CloseMainWindow() | Out-Null; Start-Sleep -Milliseconds 500 } } catch {}
    try { if (!$p.HasExited) { $p | Stop-Process -Force } } catch {}
}
