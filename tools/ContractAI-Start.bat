@echo off
setlocal

:: Relaunch with elevated privileges if not already running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File Start_ContractAI.ps1 %*

endlocal

