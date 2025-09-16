# STEP2_BACKEND_FRONT.ps1 — start backend (TLS) and static front (TLS), wait until both are ready

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){ Write-Host $m -ForegroundColor Green }

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$CERT = Join-Path $ROOT "certs\dev.crt"
$KEY  = Join-Path $ROOT "certs\dev.key"

if(!(Test-Path $CERT) -or !(Test-Path $KEY)){
  throw "Missing certs. Expected: $CERT and $KEY. Run STEP1 first."
}

# 1) Backend (FastAPI via uvicorn) — adjust module if differs
$BACK_CMD  = "python"
$BACK_ARGS = @("-m","uvicorn","contract_review_app.api.app:app",
               "--host","0.0.0.0","--port","9000",
               "--ssl-certfile",$CERT,"--ssl-keyfile",$KEY)

# 2) Front static (http-server over TLS) — serves word_addin_dev
$FRONT_CMD  = "npx.cmd"
$FRONT_ARGS = @("--yes","http-server", (Join-Path $ROOT "word_addin_dev"),
                "-S","-C",$CERT,"-K",$KEY,"-p","3000","-a","127.0.0.1","--cors")

# Start both
$backP  = Start-Process -FilePath $BACK_CMD  -ArgumentList $BACK_ARGS  -PassThru
$frontP = Start-Process -FilePath $FRONT_CMD -ArgumentList $FRONT_ARGS -PassThru

Info "[WAIT] Backend -> https://127.0.0.1:9000/health"
# wait backend
for($i=0;$i -lt 60;$i++){
  try{ $r=Invoke-WebRequest "https://127.0.0.1:9000/health" -UseBasicParsing -TimeoutSec 3
       if($r.StatusCode -ge 200 -and $r.StatusCode -lt 300){ break } }catch{}
  Start-Sleep -Milliseconds 600
}
Ok   "[OK] Backend https://127.0.0.1:9000"

# Panel URL (best effort, uses newest build folder)
$APPDIR = Join-Path $ROOT "word_addin_dev\app"
$latest = Get-ChildItem $APPDIR -Directory | ? { $_.Name -like "build-*" } | sort LastWriteTime -desc | select -f 1
$panel  = if($latest){ "https://127.0.0.1:3000/app/{0}/taskpane.html" -f $latest.Name } else { "https://127.0.0.1:3000/taskpane.html" }

Info "[WAIT] Front -> $panel"
for($i=0;$i -lt 40;$i++){
  try{ $r=Invoke-WebRequest $panel -UseBasicParsing -TimeoutSec 3
       if($r.StatusCode -ge 200 -and $r.StatusCode -lt 300){ break } }catch{}
  Start-Sleep -Milliseconds 500
}
Ok "[OK] Front (TLS) https://127.0.0.1:3000"

Write-Host "`nPress Enter to stop servers..." -ForegroundColor Yellow
[void][System.Console]::ReadLine()
Try{ $backP | Stop-Process -Force }Catch{}
Try{ $frontP| Stop-Process -Force }Catch{}
