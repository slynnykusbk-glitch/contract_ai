# HARD_RESET_AND_REGISTER.ps1 — clean caches, sync manifest to latest build, re-register add-in
# Run from project root (e.g., C:\Users\Ludmila\contract_ai)

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){ Write-Host "[ERR]  $m" -ForegroundColor Red }

# 0) Kill Word (safe)
Info "Killing WINWORD..."
cmd /c "taskkill /IM WINWORD.EXE /F >nul 2>nul"
try { Stop-Process -Name WINWORD -Force -ErrorAction Stop } catch { Write-Host "[INFO] WINWORD not running" }

# 1) Paths
$ROOT = (Get-Location).Path
$MANIFEST = Join-Path $ROOT "word_addin_dev\manifest.xml"
$APPDIR   = Join-Path $ROOT "word_addin_dev\app"
if(!(Test-Path $MANIFEST)){ throw "Manifest not found: $MANIFEST" }
if(!(Test-Path $APPDIR)){ throw "App dir not found: $APPDIR" }

# 2) Latest build + update manifest (Version + SourceLocation)
$latest = Get-ChildItem $APPDIR -Directory | Where-Object { $_.Name -like "build-*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $latest){ throw "No build-* folder found under $APPDIR" }
$panelUrl = "https://localhost:3000/app/{0}/taskpane.html" -f $latest.Name
$ver = ("1.0.{0}.{1}" -f (Get-Date).ToString('yyyy'), (Get-Date).ToString('MMdd'))

$xml = Get-Content -LiteralPath $MANIFEST -Raw -Encoding UTF8
$xml = $xml -replace '<Version>.*?</Version>', "<Version>$ver</Version>"
$xml = [regex]::Replace($xml, 'SourceLocation\s+DefaultValue="[^"]+"', 'SourceLocation DefaultValue="'+$panelUrl+'"')
Set-Content -LiteralPath $MANIFEST -Value $xml -Encoding UTF8
Ok "Manifest Version=$ver"
Ok "Manifest SourceLocation=$panelUrl"

# 3) Purge caches (WEF, WebView2, temp sideload docs)
function RmSafe($p){ if(Test-Path $p){ Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue } }
Info "Purging Office add-ins caches..."
RmSafe "$env:LOCALAPPDATA\Microsoft\Office\16.0\WEF\Cache"
RmSafe "$env:LOCALAPPDATA\Microsoft\Office\16.0\WEF\WebViewCache"
RmSafe "$env:LOCALAPPDATA\Microsoft\Office\WebView2"
RmSafe "$env:LOCALAPPDATA\Packages\Microsoft.Win32WebViewHost_cw5n1h2txyewy\AC"
Get-ChildItem "$env:TEMP" -Filter "Word add-in *.docx" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Ok "Caches purged (where present)"

# 4) Ensure WebView=edge; clear/unregister/register
$npx = (Get-Command npx.cmd -ErrorAction SilentlyContinue).Path
if(-not $npx){ $npx = (Get-Command npx -ErrorAction SilentlyContinue).Path }
if(-not $npx){ throw "npx not found in PATH" }

function RunNpx([string[]]$argList,[string]$name){
  $p = Start-Process -FilePath $npx -ArgumentList $argList -NoNewWindow -PassThru -Wait
  if($p.ExitCode -ne 0){ throw "npx failed: $name (ExitCode=$($p.ExitCode))" }
}

Info "Dev-settings: clear -> unregister -> register -> webview edge..."
RunNpx @('--yes','office-addin-dev-settings','clear',      $MANIFEST) 'clear'
RunNpx @('--yes','office-addin-dev-settings','unregister', $MANIFEST) 'unregister'
RunNpx @('--yes','office-addin-dev-settings','register',   $MANIFEST) 'register'
RunNpx @('--yes','office-addin-dev-settings','webview',    $MANIFEST,'edge') 'webview'
Ok "Add-in registered for development"

# 5) Show registered list
Info "Registered dev add-ins:"
& $npx --yes office-addin-dev-settings registered

# 6) Next steps
Write-Host ""
Write-Host "==== NEXT STEPS ====" -ForegroundColor Magenta
Write-Host "1) In a NEW PowerShell window:  .\STEP2_BACKEND_FRONT.bat   (leave it running)" -ForegroundColor White
Write-Host "2) Verify:" -ForegroundColor White
Write-Host "   Invoke-WebRequest https://localhost:9000/health -UseBasicParsing" -ForegroundColor Gray
Write-Host "   Invoke-WebRequest `"$panelUrl`" -UseBasicParsing" -ForegroundColor Gray
Write-Host "3) Sideload Word add-in:" -ForegroundColor White
Write-Host "   npx.cmd --yes office-addin-dev-settings sideload `"$MANIFEST`" desktop --app word" -ForegroundColor Gray
Write-Host "4) If taskpane not auto-opened: Word -> Insert -> My Add-ins -> See all -> Shared Folder -> Contract AI - Draft Assistant -> Insert" -ForegroundColor Gray
Write-Host "====================" -ForegroundColor Magenta
