# RUN_DEV_ADMIN.ps1  — один клік для Dev
param([switch]$OpenSelfTest)

# 0) Самопідняття з правами Адміністратора, якщо треба тільки для блоків, де це потрібно:
function Ensure-Admin {
  if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
      ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
  }
}

# 1) Корінь проєкту
$repo = "C:\Users\Ludmila\contract_ai"
Set-Location $repo

# 2) Закрити Word і почистити кеші (без адм)
taskkill /IM WINWORD.EXE /F 2>$null | Out-Null
Remove-Item "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\EdgeWebView\User Data\Default\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue

# 3) Імпорт сертифіката у сховище КОРИСТУВАЧА (без адм, цього достатньо для Word/WebView2)
$cert = ".\word_addin_dev\certs\localhost.pem"
certutil -user -addstore Root $cert | Out-Null

# 4) Створити/перестворити SMB-шару \\localhost\wef і Trusted Catalog (потрібні адм. права)
Ensure-Admin

# 4.1) Увімкнути службу сервера, якщо вимкнена (інакше net share падає кодом 2310)
sc.exe config lanmanserver start= auto | Out-Null
sc.exe start  lanmanserver           | Out-Null

# 4.2) Перестворити шару й дати ПОВНИЙ доступ саме вашому обліковому запису
$sharePath = Join-Path $repo "word_addin_dev"
$me = "$env:COMPUTERNAME\$env:USERNAME"

# Видалити стару шару, якщо є
cmd /c "net share wef /delete" 2>$null | Out-Null

# Створити заново
cmd /c "net share wef=""$sharePath"" /grant:""$me"",FULL /CACHE:None" | Out-Null

# 4.3) Додати каталог у TrustedCatalogs (HKCU) як Shared Folder
$catKey = "HKCU:\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\wef_local"
New-Item -Path $catKey -Force | Out-Null
New-ItemProperty -Path $catKey -Name "Id"         -Value "wef_local" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $catKey -Name "Url"        -Value "\\localhost\wef" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $catKey -Name "ShowInMenu" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $catKey -Name "Type"       -Value 2 -PropertyType DWord -Force | Out-Null

# 5) Маніфест має вказувати на localhost (не 127.0.0.1)
$mf = ".\word_addin_dev\manifest.xml"
(Get-Content $mf) -replace '127\.0\.0\.1','localhost' | Set-Content $mf

# 6) Запустити бекенд і панель (без адм уже ок)
$py = Join-Path $repo ".venv\Scripts\python.exe"
$env:LLM_PROVIDER = "mock"

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList @(
  "-m","uvicorn","contract_review_app.api.app:app",
  "--host","localhost","--port","9443",
  "--ssl-certfile",".\word_addin_dev\certs\localhost.pem",
  "--ssl-keyfile",".\word_addin_dev\certs\localhost-key.pem",
  "--reload"
)

Start-Process -WindowStyle Minimized -FilePath $py -ArgumentList @(
  "word_addin_dev\serve_https_panel.py", "--host","localhost"
)

# 7) Дочекатися портів (без “sleep”)
function Wait-Port($h,$p){
  while(-not (Test-NetConnection $h -Port $p -InformationLevel Quiet)){ Start-Sleep -Milliseconds 200 }
}
Wait-Port localhost 9443
Wait-Port localhost 3000

# 8) За бажанням — відкрити self-test у браузері
if ($OpenSelfTest) {
  $ts = [DateTime]::Now.Ticks
  Start-Process "https://localhost:3000/panel_selftest.html?v=dev&ts=$ts"
}

# 9) Відкрити Провідник на \\localhost\wef — швидка перевірка каталогу
Start-Process explorer.exe "\\localhost\wef"

Write-Host "Готово. У Word: Вставка → Мои надстройки → Общая папка → Contract AI — Draft Assistant (Dev)."
