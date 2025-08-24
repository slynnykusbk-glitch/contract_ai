@echo off
setlocal
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%\~dp0RUN\_DEV.ps1" %\*
endlocal
