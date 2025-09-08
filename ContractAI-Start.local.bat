@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- venv ----
if not exist .venv\Scripts\python.exe (
  where py >nul 2>&1 && (py -3.11 -m venv .venv || py -3 -m venv .venv) || python -m venv .venv
)
call .venv\Scripts\activate

python -m pip install -q -U pip wheel
python -m pip install -q -r requirements.txt
python -m pip install -q uvicorn[standard]

REM ---- env ----
set "API_KEY=local-test-key-123"
set "LLM_PROVIDER=mock"

REM ---- certs ----
if not exist dev_certs mkdir dev_certs
if not exist dev_certs\cert.pem (
  if exist C:\certs\dev.crt copy /y C:\certs\dev.crt dev_certs\cert.pem >nul
)
if not exist dev_certs\key.pem (
  if exist C:\certs\dev.key copy /y C:\certs\dev.key dev_certs\key.pem >nul
)
if not exist dev_certs\cert.pem (
  echo [dev] generating self-signed certs...
  python gen_dev_cert.py
  if exist C:\certs\dev.crt copy /y C:\certs\dev.crt dev_certs\cert.pem >nul
  if exist C:\certs\dev.key copy /y C:\certs\dev.key dev_certs\key.pem >nul
)

REM ---- start server in separate window ----
start "ContractAI API" cmd /k ^
  python -m uvicorn contract_review_app.api.app:app ^
    --host 127.0.0.1 --port 9443 ^
    --ssl-certfile dev_certs\cert.pem --ssl-keyfile dev_certs\key.pem

REM ---- open panel ----
timeout /t 2 >nul
start "" https://localhost:9443/panel/panel_selftest.html?v=dev