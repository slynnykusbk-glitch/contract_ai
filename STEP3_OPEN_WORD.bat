@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Always work from the folder of this BAT
cd /d "%~dp0"

REM Prepare logs
set LOGDIR=%~dp0logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TS=%%i
set LOG=%LOGDIR%\step3_%TS%.log

REM Use the system PowerShell
set PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe

echo [INFO] Starting STEP3 at %DATE% %TIME% > "%LOG%"
echo [INFO] Script dir: %~dp0 >> "%LOG%"
echo [INFO] Log file:   "%LOG%" >> "%LOG%"
echo.>>"%LOG%"

REM Run the PS1 and capture ALL output (stdout+stderr)
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0STEP3_OPEN_WORD.ps1" *>> "%LOG%"
set EXITCODE=%ERRORLEVEL%

echo.>> "%LOG%"
echo [INFO] Exit code: %EXITCODE% >> "%LOG%"

REM Show the log in the console
type "%LOG%"

echo.
if %EXITCODE% neq 0 (
  echo [ERR] STEP3 failed. See full log: "%LOG%"
) else (
  echo [OK] STEP3 completed successfully.
)
echo.
pause
endlocal
