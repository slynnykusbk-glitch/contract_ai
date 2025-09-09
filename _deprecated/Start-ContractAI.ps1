Param([switch]$OpenWord)

$ErrorActionPreference = 'Stop'
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $proj ".venv\Scripts\python.exe"
$wef = Join-Path $env:LOCALAPPDATA "Microsoft\Office\16.0\Wef"
$manifest = Join-Path $proj "word_addin_dev\manifest.xml"

Write-Host ">>> Kill old uvicorn on 9000 if any..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "9000"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host ">>> Clear __pycache__ ..."
Get-ChildItem $proj -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ">>> Clear WEF cache..."
if (!(Test-Path $wef)) { New-Item $wef -ItemType Directory | Out-Null }
Remove-Item "$wef\*" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ">>> Copy manifest to WEF..."
Copy-Item $manifest -Destination (Join-Path $wef (Split-Path $manifest -Leaf)) -Force

Write-Host ">>> Start backend on http://127.0.0.1:9000 ..."
Start-Process -FilePath $venvPython -ArgumentList @('-m','uvicorn','contract_review_app.api.app:app','--host','127.0.0.1','--port','9000','--reload') -WorkingDirectory $proj

if ($OpenWord) {
  Write-Host ">>> Launch Word..."
  Start-Process "winword.exe"
}

Write-Host ">>> Done."
