@echo off
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0tools\start_oneclick.ps1" %*
endlocal
