# One-click runner for contract_ai offline analysis
param(
  [string]$ProjectRoot = "$PSScriptRoot",
  [string]$PythonExe = "$PSScriptRoot\.venv\Scripts\python.exe"
)

Write-Host "== contract_ai Offline Analysis ==" -ForegroundColor Cyan
if (!(Test-Path $PythonExe)) {
  # fallback to PATH python
  $PythonExe = "python"
}

$Tool = Join-Path $PSScriptRoot "tools\analyze_project.py"
if (!(Test-Path $Tool)) {
  Write-Error "tools\analyze_project.py not found. Please place files as specified."
  exit 1
}

& $PythonExe $Tool --project-root $ProjectRoot --out (Join-Path $ProjectRoot "reports")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Report = Join-Path $ProjectRoot "reports\analysis.html"
if (Test-Path $Report) {
  Write-Host "Opening report..." -ForegroundColor Green
  Start-Process $Report
} else {
  Write-Warning "Report not found at $Report"
}
