@echo off
setlocal enableextensions
cd /d "%~dp0"

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "LOG=%TEMP%\ContractAI-start.log"

echo [INFO] Starting Contract AI... > "%LOG%"
echo [INFO] Project root: %CD% >> "%LOG%"

"%PS%" -NoProfile -ExecutionPolicy Bypass -File ".\Start-ContractAI.ps1" -OpenWord ^
  1>> "%LOG%" 2>&1

if errorlevel 1 (
  echo [ERROR] Start-ContractAI.ps1 exited with code %errorlevel%
  echo See log: %LOG%
) else (
  echo [OK] Started. Backend window should be open. Log: %LOG%
)

echo.
pause
endlocal
