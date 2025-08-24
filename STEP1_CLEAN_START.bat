@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "Start-Process PowerShell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%~dp0STEP1_CLEAN_START.ps1\"'"
endlocal
