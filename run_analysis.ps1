param()
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$ROOT/.venv/Scripts/Activate.ps1") {
    . "$ROOT/.venv/Scripts/Activate.ps1"
}
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$OUT = Join-Path $ROOT "tools/reports/$timestamp"
$py = "python"
if (Test-Path "$ROOT/.venv/Scripts/python.exe") {
    $py = "$ROOT/.venv/Scripts/python.exe"
}
& $py "$ROOT/tools/analyze_project.py" --project-root "$ROOT" --out "$OUT"
$code = $LASTEXITCODE
if ($code -eq 0 -or $code -eq 2) {
    if (Test-Path "$OUT/analysis.html") {
        Start-Process "$OUT/analysis.html"
    }
}
exit $code
