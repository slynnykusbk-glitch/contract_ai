@echo off
setlocal
title ContractAI — Start

rem ===== 0) Папка проекта
cd /d C:\Users\Ludmila\contract_ai

rem ===== 1) Ключ/слот LLM — как просили, 84
set "LLM_KEY_SLOT=84"
set "AZURE_OPENAI_KEY_SLOT=84"
rem сохраняем ещё и в постоянные переменные пользователя
setx LLM_KEY_SLOT 84 >nul
setx AZURE_OPENAI_KEY_SLOT 84 >nul

rem ===== 2) Виртуалка и минимальные зависимости (если вдруг нет)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
)
call .venv\Scripts\pip.exe -q install -U pip
call .venv\Scripts\pip.exe -q install fastapi uvicorn jinja2 pydantic python-multipart ^
  cryptography pyyaml requests httpx python-docx

rem ===== 3) Обновить/гарантировать Shared Folder \\localhost\wef и доверенный каталог Office
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='C:\Users\Ludmila\contract_ai\word_addin_dev';" ^
  "if(-not (Get-SmbShare -Name 'wef' -ea SilentlyContinue)) { New-SmbShare -Name 'wef' -Path $p -FullAccess $env:USERNAME | Out-Null }" ^
  "; $base='HKCU:\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs'; if(-not (Test-Path $base)) { New-Item $base -Force | Out-Null }" ^
  "; $has=$false; Get-ItemProperty \"$base\*\" 2>$null | %%{ if($_.Url -eq '\\\\localhost\\wef'){ $has=$true } }" ^
  "; if(-not $has){ $g=[guid]::NewGuid().ToString().ToUpper(); $k=Join-Path $base ('{'+$g+'}'); New-Item $k -Force|Out-Null; New-ItemProperty $k -Name Url -Value '\\\\localhost\\wef' -PropertyType String -Force|Out-Null; New-ItemProperty $k -Name Id -Value $g -PropertyType String -Force|Out-Null; New-ItemProperty $k -Name CatalogType -Value 2 -PropertyType DWord -Force|Out-Null; New-ItemProperty $k -Name ShowInCatalog -Value 1 -PropertyType DWord -Force|Out-Null }" ^
  "; Remove-Item \"$env:LOCALAPPDATA\Microsoft\Office\16.0\WEF\Cache\*\" -Recurse -Force -ea SilentlyContinue"

rem ===== 4) Запускаем бэкенд (в отдельном окне)
start "ContractAI API" cmd /k ".venv\Scripts\python.exe -m uvicorn contract_review_app.api.app:app --host 127.0.0.1 --port 9443 --ssl-certfile dev\localhost.crt --ssl-keyfile dev\localhost.key"

rem (необязательно) прогреем панель в браузере
start "" "https://127.0.0.1:9443/panel/taskpane.html?v=dev"

rem ===== 5) Откроем Word
start "" winword.exe

endlocal
