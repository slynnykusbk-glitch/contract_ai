@echo off
setlocal
title Contract AI — Dev Start
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0tools\start_onedclick.ps1" %*
endlocal
