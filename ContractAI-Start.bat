@echo off
setlocal
cd /d "%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File tools\start_oneclick.ps1 -OpenWord:$True %*
