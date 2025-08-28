param([switch]$OpenSelfTest=$true)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
cd $repo

# 0) чистий старт
taskkill /IM WINWORD.EXE /F 2>$null
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*" -Recurse -Force -EA SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*" -Recurse -Force -EA SilentlyContinue

# 1) сертифікат
$cert = Join-Path $repo "word_addin_dev\certs\localhost.pem"
Import-Certificate -FilePath $cert -CertStoreLocation Cert:\CurrentUser\Root  | Out-Null
Import-Certificate -FilePath $cert -CertStoreLocation Cert:\LocalMachine\Root | Out-Null

# 2) шера \\localhost\wef (доступ – ваш акаунт)
$root = Join-Path $repo "word_addin_dev"
try { Remove-SmbShare -Name wef -Force -EA SilentlyContinue } catch {}
$me = "$env:COMPUTERNAME\$env:USERNAME"
try {
  New-SmbShare -Name wef -Path $root -FullAccess $me -CachingMode None | Out-Null
} catch {
  cmd /c "net share wef=""$root"" /GRANT:$env:COMPUTERNAME\%USERNAME%,FULL" | Out-Null
}

# 3) manifest → localhost
$mf = Join-Path $root "manifest.xml"
(Get-Content $mf) -replace '127\.0\.0\.1','localhost' | Set-Content $mf -Encoding UTF8

# 4) старт бекенда (https://localhost:9443) і панелі (https://127.0.0.1:3000)
$py = Join-Path $repo ".venv\Scripts\python.exe"
$env:AI_PROVIDER = "mock"

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList `
  "-m","uvicorn","contract_review_app.api.app:app","--host","localhost","--port","9443",`
  "--ssl-certfile",".\word_addin_dev\certs\localhost.pem","--ssl-keyfile",".\word_addin_dev\certs\localhost-key.pem","--reload"

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList "word_addin_dev\serve_https_panel.py"

if ($OpenSelfTest) {
  Start-Process "https://localhost:3000/panel_selftest.html?v=dev&ts=$(Get-Date).Ticks"
}

Write-Host "Готово. Word → Вставка → Мои надстройки → Общая папка → Contract AI — Draft Assistant (Dev)."
