Param(
  [string]$BackendUrl   = "https://localhost:9000",
  [string]$FrontUrl     = "https://localhost:3000",
  [string]$ManifestPath = "C:\Users\Ludmila\contract_ai\word_addin_dev\manifest.xml",
  # 🔹 тут виправлено: taskpane.html лежить у корені word_addin_dev, а не в dist
  [string]$WebrootPath  = "C:\Users\Ludmila\contract_ai\word_addin_dev",
  [string]$AppPath      = "C:\Users\Ludmila\contract_ai\api\app.py",
  [string]$OutPrefix    = "$PSScriptRoot\report\doctor_report"
)

$ErrorActionPreference = "Stop"

# Better Cyrillic/UTF-8 in console
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}
try { [Console]::InputEncoding  = [Text.UTF8Encoding]::new($false) } catch {}

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg){ Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg){ Write-Warning $msg }
function Write-Fail($msg){ Write-Host "[FAIL] $msg" -ForegroundColor Red }

# Ensure report dir
$reportDir = Split-Path -Parent $OutPrefix
if (-not (Test-Path $reportDir)) { New-Item -Path $reportDir -ItemType Directory | Out-Null }

# Timestamp
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$OutPrefixFinal = "$OutPrefix-$ts"
$ConsoleLog = "$OutPrefixFinal.console.log"

# Start transcript (console log)
try { Start-Transcript -Path $ConsoleLog -Force | Out-Null } catch {}

# ExecutionPolicy tip (only current process)
if ($env:PSExecutionPolicyPreference -ne "Bypass") {
  Write-Info "ExecutionPolicy (process): setting to Bypass for this run."
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
}

# Locate Python
$PythonCmd = $null
$PythonArgsPrefix = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
  $PythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $PythonCmd = "py"
  $PythonArgsPrefix = @("-3")
} else {
  Write-Fail "Python не знайдено у PATH. Встанови Python 3 і спробуй знову."
  try { Stop-Transcript | Out-Null } catch {}
  Read-Host "Натисни Enter, щоб закрити вікно"
  exit 1
}
Write-Info "Python: $PythonCmd $($PythonArgsPrefix -join ' ')"

# Verify 'requests' (для live API перевірок)
try {
  $res = & $PythonCmd @($PythonArgsPrefix) -c "import importlib.util as u; import sys; print('ok' if u.find_spec('requests') else 'miss')"
  if ($res -ne "ok") {
    Write-Info "Встановлюю 'requests' (pip --user)…"
    & $PythonCmd @($PythonArgsPrefix) -m pip install --user requests | Out-Host
  }
} catch {
  Write-Warn "Не вдалося перевірити/встановити 'requests'. Продовжую без live API перевірок."
}

# Resolve doctor script
$Doctor = Join-Path $PSScriptRoot "contract_ai_doctor.py"
if (-not (Test-Path $Doctor)) {
  Write-Fail "Не знайдено $Doctor. Поклади скрипт поряд із RUN_DOCTOR.ps1"
  try { Stop-Transcript | Out-Null } catch {}
  Read-Host "Натисни Enter, щоб закрити вікно"
  exit 1
}

# Echo config
Write-Info "Backend  = $BackendUrl"
Write-Info "Frontend = $FrontUrl"
Write-Info "Manifest = $ManifestPath"
Write-Info "Webroot  = $WebrootPath"
Write-Info "App      = $AppPath"
Write-Info "Out      = $OutPrefixFinal"

# Run doctor
$argsList = @($Doctor, "--backend", $BackendUrl, "--front", $FrontUrl,
              "--manifest", $ManifestPath, "--webroot", $WebrootPath,
              "--app", $AppPath, "--out", $OutPrefixFinal)

try {
  & $PythonCmd @($PythonArgsPrefix + $argsList) | Out-Host
} catch {
  Write-Fail "Помилка запуску doctor: $($_.Exception.Message)"
  try { Stop-Transcript | Out-Null } catch {}
  Read-Host "Натисни Enter, щоб закрити вікно"
  exit 1
}

# Open report
$md = "$OutPrefixFinal.md"
$json = "$OutPrefixFinal.json"
if (Test-Path $md) {
  Write-Ok "Звіт: $md"
  try { Start-Process $md } catch { Write-Warn "Не вдалося відкрити ${md}: $($_.Exception.Message)" }
} else {
  Write-Warn "Markdown-звіт не знайдено."
}
if (Test-Path $json) {
  Write-Info "JSON: $json"
}

try { Stop-Transcript | Out-Null } catch {}

# Keep window open when launched via context menu
Read-Host "Натисни Enter, щоб закрити вікно"
