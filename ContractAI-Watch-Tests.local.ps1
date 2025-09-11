# Запускает отдельным окном улучшенный watch всех бэкенд-тестов (ptw)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

$tools = Join-Path $repo "tools\watch_backend_tests.ps1"
if (-not (Test-Path $tools)) { throw "Missing $tools" }

# Полный режим (ptw). Существующая кнопка не трогаем.
Start-Process powershell -ArgumentList "-NoExit","-Command","`"$tools -All`""

Write-Host "Launched improved backend test watcher (ptw). Close window to stop."
