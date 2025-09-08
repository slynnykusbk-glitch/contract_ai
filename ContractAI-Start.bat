@echo off
setlocal enableextensions
cd /d "%~dp0"

set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
echo [ERR] .venv not found. Run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
exit /b 1
)

set CERT=word_addin_dev\certs\panel-cert.pem
set KEY=word_addin_dev\certs\panel-key.pem
set PORT=9443

rem (опционально) показать какой питон используем
echo [INFO] Using "%PY%"

rem старт uvicorn с TLS на localhost
"%PY%" -m uvicorn contract_review_app.api.app:app ^
--host localhost --port %PORT% ^
--ssl-certfile "%CERT%" --ssl-keyfile "%KEY%" ^
--log-level info --reload ^
--proxy-headers

rem открыть панель
start "" "https://localhost:%PORT%/panel/panel_selftest.html?v=dev"
