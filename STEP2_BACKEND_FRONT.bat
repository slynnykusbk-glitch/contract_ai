@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='%~dp0STEP2_BACKEND_FRONT.ps1'; Start-Process PowerShell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File', $p"
endlocal
