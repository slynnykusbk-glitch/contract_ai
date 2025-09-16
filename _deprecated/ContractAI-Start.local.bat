@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ===== Version-agnostic one-click starter for Contract AI =====

REM --- cd to repo root (folder where this .bat lives) ---
cd /d "%~dp0"

REM --- Prefer Python Launcher 'py -3', fallback to 'python' ---
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
  echo [ERROR] Python 3.x not found. Install from https://www.python.org/downloads/windows/
  echo Or run:  winget install Python.Python.3.12
  pause
  exit /b 1
)

REM --- Create venv if missing ---
if not exist ".venv" (
  echo [INFO] Creating venv...
  %PY_CMD% -m venv .venv || goto :fail
)

REM --- Upgrade pip and install deps (dev deps cover tests & panel) ---
echo [INFO] Upgrading pip and installing requirements...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
pip install -r requirements.txt >nul
if exist requirements-dev.txt pip install -r requirements-dev.txt >nul
REM panel & tests extras
pip install fpdf2 openapi-spec-validator >nul

REM --- Generate dev certs if missing ---
if not exist dev_certs\cert.pem (
  echo [INFO] Generating dev TLS certs...
  python tools\mk_dev_certs.py || python gen_dev_cert.py
)

REM --- Force UTF-8 to avoid cp1251 issues on Windows ---
set PYTHONUTF8=1

REM --- Start API server in a new window ---
echo [INFO] Starting API (https://127.0.0.1:9443) ...
start "ContractAI-API" cmd /k ^
  ".venv\Scripts\activate && python -m uvicorn contract_review_app.api.app:app --host 0.0.0.0 --port 9443 --ssl-certfile dev_certs\cert.pem --ssl-keyfile dev_certs\key.pem"

REM --- Start Panel (Word add-in local HTTPS) in a new window ---
echo [INFO] Starting Panel (https://127.0.0.1:9443/panel/...) ...
start "ContractAI-Panel" cmd /k ^
  ".venv\Scripts\activate && python tools\serve_https_panel.py"

REM --- Open self-test page in default browser ---
timeout /t 2 >nul
start "" https://127.0.0.1:9443/panel/panel_selftest.html?v=dev

echo.
echo [OK] Contract AI is starting in two windows:
echo      - ContractAI-API  (Uvicorn server)
echo      - ContractAI-Panel (static panel)
echo Open Word add-in if needed: word_addin_dev/Readme (or Run_Contract_AI.cmd)
echo.
pause
exit /b 0

:fail
echo [ERROR] Failed to create venv or install deps.
pause
exit /b 1
