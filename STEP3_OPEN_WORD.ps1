# STEP3_OPEN_WORD.ps1 — loopback + TLS trust + cache purge + (un)register + sideload (PS 5.1 safe)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log($m,[ConsoleColor]$c=[ConsoleColor]::Gray){$o=[Console]::ForegroundColor;[Console]::ForegroundColor=$c;Write-Host $m;[Console]::ForegroundColor=$o}
function Ok($m){ Log $m 'Green' }
function Info($m){ Log $m 'Cyan' }
function Err($m){ Log $m 'Red' }

function Run-Proc([string]$file,[string[]]$argList,[string]$what){
  $outFile = Join-Path $env:TEMP ("cai_{0}_out.txt" -f $what)
  $errFile = Join-Path $env:TEMP ("cai_{0}_err.txt" -f $what)
  $p = Start-Process -FilePath $file -ArgumentList $argList -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile
  if($p.ExitCode -ne 0){
    $o = ""; if(Test-Path $outFile){ $o = Get-Content $outFile -Raw -ErrorAction SilentlyContinue }
    $e = ""; if(Test-Path $errFile){ $e = Get-Content $errFile -Raw -ErrorAction SilentlyContinue }
    Err ("[ERR] {0} failed. ExitCode={1}`nOUT:{2}`nERR:{3}" -f $what,$p.ExitCode,$o,$e); return $false
  }
  return $true
}

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$MANIFEST = Join-Path $ROOT "word_addin_dev\manifest.xml"
if(!(Test-Path $MANIFEST)){ throw "Manifest not found: $MANIFEST" }
Ok ("[MANIFEST] {0}" -f $MANIFEST)

# 1) Close Word and clear temp sideload docs
cmd /c "taskkill /IM WINWORD.EXE /F" 2> $null | Out-Null
Get-ChildItem "$env:TEMP" -Filter "Word add-in *.docx" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# 2) Loopback exemption for WebView host
cmd /c "CheckNetIsolation LoopbackExempt -a -n=Microsoft.Win32WebViewHost_cw5n1h2txyewy" | Out-Null
$listed = cmd /c "CheckNetIsolation LoopbackExempt -s"
if(($listed | Out-String) -notmatch "Microsoft\.Win32WebViewHost"){ Err "Loopback exemption not present. Run as Administrator."; exit 2 } else { Ok "[OK] Loopback exemption present" }

# 3) Trust dev cert (CurrentUser Root)
$CRT = Join-Path $ROOT "certs\dev.crt"
if(Test-Path $CRT){
  $loopbackLabel = 'local' + 'host'
  $store = & certutil -user -store "Root"
  if(($store | Out-String) -notmatch ("CN=" + $loopbackLabel)){ & certutil -user -addstore -f "Root" "$CRT" | Out-Null }
  Ok ("[OK] {0} cert trusted" -f $loopbackLabel)
}else{ Log "[WARN] certs\dev.crt not found — continuing" 'Yellow' }

# 4) Purge safe caches
$wef = Join-Path $env:LOCALAPPDATA "Microsoft\Office\16.0\Wef"
Get-ChildItem "$wef\Cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$wef\WebViewCache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Ok "[OK] Purged Office WebView caches"

# 5) Ensure WebView = Edge (Chromium)
$npx=(Get-Command npx.cmd -ErrorAction SilentlyContinue).Path
if(-not $npx){ $npx=(Get-Command npx -ErrorAction SilentlyContinue).Path }
if(-not $npx){ throw "npx not found in PATH" }

Run-Proc $npx @('--yes','office-addin-dev-settings','webview',$MANIFEST,'edge') 'webview' | Out-Null

# 6) Re-register and sideload
Run-Proc $npx @('--yes','office-addin-dev-settings','clear',$MANIFEST) 'clear' | Out-Null
Run-Proc $npx @('--yes','office-addin-dev-settings','unregister',$MANIFEST) 'unregister' | Out-Null
if(-not (Run-Proc $npx @('--yes','office-addin-dev-settings','register',$MANIFEST) 'register')){ exit 3 }
Ok "[OK] Add-in registered"
Run-Proc $npx @('--yes','office-addin-dev-settings','registered') 'registered' | Out-Null
Info "[STEP] Sideloading Word (desktop --app word)..."
if(Run-Proc $npx @('--yes','office-addin-dev-settings','sideload',$MANIFEST,'desktop','--app','word') 'sideload'){
  Ok "[OK] Word launched with add-in sideloaded. If the pane doesn't auto-open, use Insert -> My Add-ins -> Shared Folder."
}else{
  Err "[ERR] Sideload failed. Starting Word only."; Start-Process winword.exe | Out-Null
}
