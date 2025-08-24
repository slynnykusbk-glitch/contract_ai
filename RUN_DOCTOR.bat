@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%RUN_DOCTOR.ps1" %*
pause
