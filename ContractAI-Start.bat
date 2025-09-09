@echo off
setlocal
rem ===== ContractAI unified launcher =====
pushd "%~dp0"

rem Free 9443 before start
for /f %%P in ('powershell -NoProfile -Command ^
  "(Get-NetTCPConnection -LocalPort 9443 -State Listen -ErrorAction SilentlyContinue).OwningProcess"') do set PID=%%P
if defined PID powershell -NoProfile -Command "try{Stop-Process -Id %PID% -Force}catch{}"
powershell -NoProfile -Command "Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force"

rem Import User environment variables
for %%V in (LLM_PROVIDER AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT AZURE_OPENAI_API_VERSION) do (
  for /f "usebackq tokens=* delims=" %%A in (`powershell -NoProfile -Command ^
    "[Environment]::GetEnvironmentVariable('%%V','User')"`) do set %%V=%%A
)

rem Auto-select provider when key exists
if not "%AZURE_OPENAI_API_KEY%"=="" if "%LLM_PROVIDER%"=="" set LLM_PROVIDER=azure

rem Show config and key length
for /f %%K in ('powershell -NoProfile -Command ^
  "$k=[Environment]::GetEnvironmentVariable('AZURE_OPENAI_API_KEY','User'); if($k){$k.Length}else{0}"') do set KEYLEN=%%K
echo LLM_PROVIDER=%LLM_PROVIDER%  KEYLEN=%KEYLEN%

rem Launch uvicorn
set PY=%CD%\.venv\Scripts\python.exe
"%PY%" -m uvicorn contract_review_app.api.app:app --host 127.0.0.1 --port 9443 ^
  --ssl-certfile C:\certs\dev.crt --ssl-keyfile C:\certs\dev.key
if errorlevel 1 (
  echo Uvicorn exited with error %ERRORLEVEL% (port busy or other error).
  pause
)
