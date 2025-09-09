@echo off
setlocal
rem ===== ContractAI unified launcher =====
pushd "%~dp0"

rem 1) Подтягиваем User ENV (если не заданы в этом процессе)
for %%V in (LLM_PROVIDER AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT AZURE_OPENAI_API_VERSION) do (
  if not defined %%V (
    for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v %%V 2^>nul') do set "%%V=%%B"
  )
)

rem 2) Автовыбор провайдера: есть Azure-ключ -> azure, иначе mock
if not defined LLM_PROVIDER (
  if defined AZURE_OPENAI_API_KEY (set "LLM_PROVIDER=azure") else (set "LLM_PROVIDER=mock")
)

rem 3) Глушим висящий uvicorn (если есть)
taskkill /im uvicorn.exe /f >nul 2>&1

rem 4) Запуск uvicorn в ЭТОМ ЖЕ окне (унаследует ENV)
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -m uvicorn contract_review_app.api.app:app --host 127.0.0.1 --port 9443 ^
  --ssl-certfile C:\certs\dev.crt --ssl-keyfile C:\certs\dev.key
