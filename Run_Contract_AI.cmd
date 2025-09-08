@echo off
setlocal
cd /d "%~dp0"

set REPO=%CD%
set ROOT=%REPO%\word_addin_dev
set MF=%ROOT%\manifest.xml
set CERT=%ROOT%\certs\panel-cert.pem
set KEY=%ROOT%\certs\panel-key.pem
set PY=%REPO%\.venv\Scripts\python.exe

rem 1) Закрити Word і очистити кеш
taskkill /IM WINWORD.EXE /F >NUL 2>&1
powershell -NoLogo -NoProfile -Command ^
  "Remove-Item '$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*' -Recurse -Force -EA SilentlyContinue; ^
   Remove-Item '$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*' -Recurse -Force -EA SilentlyContinue; ^
   (Get-Content '%MF%') -replace '127\.0\.0\.1','localhost' | Set-Content '%MF%' -Encoding UTF8; ^
   certutil -user -addstore Root '%CERT%' | Out-Null; ^
   New-Item -ItemType Directory -Force '$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef' | Out-Null; ^
   Copy-Item '%MF%' (Join-Path '$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef' 'ContractAI-Dev.xml') -Force | Out-Null"

rem 2) Запустити бекенд і панель
set AI_PROVIDER=mock
start "ContractAI Backend" /MIN "%PY%" -m uvicorn contract_review_app.api.app:app --host localhost --port 9443 --ssl-certfile "%CERT%" --ssl-keyfile "%KEY%" --reload
start "ContractAI Panel"   /MIN "%PY%" "%ROOT%\serve_https_panel.py" --host localhost

rem 3) Відкрити Word
start "" winword.exe

endlocal
