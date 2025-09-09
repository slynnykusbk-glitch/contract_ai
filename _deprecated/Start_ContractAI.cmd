@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File ".\Start_ContractAI.ps1"
