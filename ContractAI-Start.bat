@echo off
setlocal
cd /d "%~dp0"
REM One-click start (ASCII-safe)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0tools\ContractAI-Start.ps1" -InstallShortcut
set rc=%ERRORLEVEL%
echo.
if %rc% neq 0 (
  echo [ERR] Starter exited with code %rc%.
  pause
) else (
  echo [OK] Uvicorn running (leave its console open).
  timeout /t 2 >nul
)
endlocal
