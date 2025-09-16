param([switch]$OpenSelfTest=$true)

function Assert-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrative privileges are required. Please run this script as Administrator."
    }
}

Assert-Elevated

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
cd $repo

$pyExe = Join-Path $repo ".venv\Scripts\python.exe"
if (!(Test-Path $pyExe)) {
  Write-Host "Python virtual environment not found. Please run `python -m venv .venv` and install requirements." -ForegroundColor Red
  exit 1
}

# 0) чистий старт
taskkill /IM WINWORD.EXE /F 2>$null
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*" -Recurse -Force -EA SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*" -Recurse -Force -EA SilentlyContinue

# 1) сертифікат
$cert = Join-Path $repo "word_addin_dev\certs\localhost.pem"
try {
  Import-Certificate -FilePath $cert -CertStoreLocation Cert:\CurrentUser\Root  | Out-Null
  Import-Certificate -FilePath $cert -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
} catch {
  Write-Error "Failed to import certificate: $_"
  throw
}

# 2) шера \\localhost\wef (доступ – ваш акаунт)
$root = Join-Path $repo "word_addin_dev"
try { Remove-SmbShare -Name wef -Force -EA SilentlyContinue } catch {
  Write-Warning "Failed to remove existing share 'wef': $_"
}
$me = "$env:COMPUTERNAME\$env:USERNAME"
try {
    New-SmbShare -Name wef -Path $root -FullAccess $me -CachingMode None | Out-Null
} catch {
    try {
        cmd /c "net share wef=""$root"" /GRANT:$env:COMPUTERNAME\%USERNAME%,FULL" | Out-Null
    } catch {
        Write-Error "Failed to create SMB share 'wef': $_"
        throw
    }
}

# 3) manifest → localhost
$mf = Join-Path $root "manifest.xml"
(Get-Content $mf) -replace '127\.0\.0\.1','localhost' | Set-Content $mf -Encoding UTF8

# 4) старт бекенда (https://127.0.0.1:9443) і панелі (https://127.0.0.1:3000)
$py = Join-Path $repo ".venv\Scripts\python.exe"
$env:LLM_PROVIDER = "mock"

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList `
  "-m","uvicorn","contract_review_app.api.app:app","--host","localhost","--port","9443",`
  "--ssl-certfile",".\word_addin_dev\certs\localhost.pem","--ssl-keyfile",".\word_addin_dev\certs\localhost-key.pem","--reload"

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList "word_addin_dev\serve_https_panel.py"

if ($OpenSelfTest) {
  Start-Process "https://localhost:3000/panel_selftest.html?v=dev&ts=$(Get-Date).Ticks"
}

Write-Host "Готово. Word → Вставка → Мои надстройки → Общая папка → Contract AI — Draft Assistant (Dev)."
