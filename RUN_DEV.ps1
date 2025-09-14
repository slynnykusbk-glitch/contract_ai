# === RUN_DEV.ps1  —  один клік для дев-запуску ===

# 0) self-elevate до Адміна
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
  $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',"`"$PSCommandPath`"" );
  Start-Process -FilePath powershell -ArgumentList $argList -Verb RunAs
  exit
}

# 1) Закрити Word і очистити кеші (щоб завжди свіжа панель)
taskkill /IM WINWORD.EXE /F 2>$null | Out-Null
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue

$repo = Split-Path -Parent $PSCommandPath
cd $repo

$ErrorActionPreference = 'Stop'
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) { py -3.11 -m venv .venv }
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
if (!(Test-Path .\var)) { New-Item -ItemType Directory -Path .\var | Out-Null }
if (-not $env:LEGAL_CORPUS_DSN) { $env:LEGAL_CORPUS_DSN = 'sqlite:///var/corpus.db' }
$env:CONTRACTAI_LLM_API = 'mock'
$env:CONTRACTAI_DEV_PANEL = '1'

# Build panel assets with tests
$py = Join-Path $repo ".venv\Scripts\python.exe"
& $py tools/build_panel.py --run-tests

# 2) Виправити маніфест на прямий taskpane і єдиний хост 127.0.0.1
$mf = Join-Path $repo "word_addin_dev\manifest.xml"
$xml = Get-Content $mf -Raw -Encoding UTF8
$xml = $xml -replace 'https://localhost:3000/app/[^"]*/taskpane.html','https://127.0.0.1:3000/taskpane.html'
$xml = $xml -replace 'https://localhost:3000/taskpane.html','https://127.0.0.1:3000/taskpane.html'
$xml = $xml -replace 'https://localhost:3000/assets/icon-32.png','https://127.0.0.1:3000/assets/icon-32.png'
$xml = $xml -replace 'https://127\.0\.0\.1:3000/app/[^"]*/taskpane.html','https://127.0.0.1:3000/taskpane.html'
Set-Content $mf $xml -Encoding UTF8

# 3) Скопіювати маніфест у локальний WEF-каталог (стабільне сіделоадінг)
$wef = "$env:LOCALAPPDATA\Microsoft\Office\16.0\WEF"
New-Item -ItemType Directory -Force -Path $wef | Out-Null
Copy-Item $mf (Join-Path $wef "contract_ai_manifest.xml") -Force

# 4) Довірити дев-сертифікат (CurrentUser Root — не питає UAC)
$certPem = Join-Path $repo "word_addin_dev\certs\localhost.pem"
Import-Certificate -FilePath $certPem -CertStoreLocation Cert:\CurrentUser\Root | Out-Null

# 5) Підняти бекенд (HTTPS localhost:9443) і панель (HTTPS localhost:3000)

$backendArgs = @(
  "-m","uvicorn","contract_review_app.api.app:app",
  "--host","localhost","--port","9443",
  "--ssl-certfile", (Join-Path $repo "word_addin_dev\certs\localhost.pem"),
  "--ssl-keyfile",  (Join-Path $repo "word_addin_dev\certs\localhost-key.pem"),
  "--reload"
)
if (-not $backendArgs) { $backendArgs = @('') }
Start-Process -FilePath $py -ArgumentList $backendArgs

Start-Sleep -Seconds 1  # невелика пауза, щоб уникнути гонок портів

$panelScript = Join-Path $repo "word_addin_dev\serve_https_panel.py"
$panelArgs = @($panelScript)
if (-not $panelArgs) { $panelArgs = @('') }
Start-Process -FilePath $py -ArgumentList $panelArgs

# 6) Відкрити self-test у браузері (для контролю зв’язку)
Start-Process -FilePath "https://localhost:3000/panel_selftest.html?v=dev"

# 7) Запустити Word — далі «Вставка → Мои надстройки → Общая папка → Contract AI — Draft Assistant»
Start-Process -FilePath winword.exe
