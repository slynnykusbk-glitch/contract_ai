@echo off
setlocal
REM Запуск PowerShell-скрипта з правильного каталогу та без політик
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_DEV.ps1"
