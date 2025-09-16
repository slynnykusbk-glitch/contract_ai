@echo off
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0tools\start_onedclick.ps1" %*
endlocal
