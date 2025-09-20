# Windows 10 / PowerShell 5 - ASCII safe starter
[CmdletBinding()]
param([switch]$InstallShortcut)

$ErrorActionPreference = 'Stop'

function OK($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function INF($m){ Write-Host "[INF] $m" -ForegroundColor Cyan }
function WRN($m){ Write-Host "[WRN] $m" -ForegroundColor Yellow }
function ERR($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

# repo root
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Push-Location $Root

# .env reader (no mutations)
function Read-DotEnv([string]$Path){
  $m=@{}
  if(Test-Path $Path){
    foreach($line in Get-Content -Encoding UTF8 $Path){
      $l=$line.Trim()
      if($l -and -not $l.StartsWith('#') -and $l.Contains('=')){
        $kv=$l.Split('=',2)
        $k=$kv[0].Trim()
        $v=$kv[1].Trim().Trim('"','''','`"')
        $m[$k]=$v
      }
    }
  }
  return $m
}

# key lookup (no $env:$name)
$KeyName = 'AZURE_OPENAI_API_KEY'
$ApiKey = [Environment]::GetEnvironmentVariable($KeyName,'Process')
if(-not $ApiKey){ $ApiKey = [Environment]::GetEnvironmentVariable($KeyName,'User') }
if(-not $ApiKey){
  $envmap = Read-DotEnv (Join-Path $Root '.env')
  if($envmap.ContainsKey($KeyName)){ $ApiKey = $envmap[$KeyName] }
}
if(-not $ApiKey){
  ERR ("API key {0} not found (env or .env)" -f $KeyName)
  Pop-Location; exit 41
}
$alen = $ApiKey.Length
$mask = if($alen -ge 10){ $ApiKey.Substring(0,6)+'***'+$ApiKey.Substring($alen-4,4) } else { ('*'*$alen) }
INF ("Key {0}: {1} (len={2})" -f $KeyName,$mask,$alen)
if($alen -ne 84){
  ERR ("Key length must be 84, got {0}" -f $alen)
  Pop-Location; exit 42
}
OK "Key length verified (84)"

# prerequisites
$py  = if(Test-Path ".venv\Scripts\python.exe"){ ".\.venv\Scripts\python.exe" }
       elseif(Test-Path "venv\Scripts\python.exe"){ ".\venv\Scripts\python.exe" } else { "python" }
$crt = Join-Path $Root "dev\localhost.crt"
$keyf= Join-Path $Root "dev\localhost.key"
if(-not (Test-Path $crt) -or -not (Test-Path $keyf)){
  ERR ("Missing TLS files: {0} ; {1}" -f $crt,$keyf)
  Pop-Location; exit 43
}

$hostip = '127.0.0.1'
$port   = 9443

# if port busy -> do not kill; only health
$listen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if($listen){
  WRN ("Port {0} already listening (PID={1}); skipping spawn" -f $port,$listen.OwningProcess)
} else {
  $args = @('-m','uvicorn','contract_review_app.api.app:app','--host',$hostip,'--port',$port,'--ssl-certfile',$crt,'--ssl-keyfile',$keyf)
  INF ("Start: {0} {1}" -f $py, ($args -join ' '))
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt | Out-Null
  $proc = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $Root -PassThru
  OK  ("Uvicorn PID={0}" -f $proc.Id)

  # wait for port up to 25s
  $deadline=(Get-Date).AddSeconds(25)
  do{
    Start-Sleep -Milliseconds 500
    $listen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  } until($listen -or (Get-Date) -ge $deadline)
  if(-not $listen){
    ERR ("Port {0} did not open in time" -f $port)
    Pop-Location; exit 44
  }
}

# --- health probe (curl first; fallback to Invoke-WebRequest)
$healthUrl = ('https://{0}:{1}/health' -f $hostip,$port)

# 1) Try with curl.exe (TLS ignore: -k). More robust on Win10 PS5.
$curlCmd = $null
try { $curlCmd = (Get-Command curl.exe -ErrorAction SilentlyContinue) } catch {}
if ($curlCmd) {
  $raw = & $curlCmd.Source -s -k $healthUrl
  if ($LASTEXITCODE -eq 0 -and $raw) {
    $json = $null
    try { $json = $raw | ConvertFrom-Json -ErrorAction Stop } catch {}
    if ($json) {
      OK ("Health 200: status={0}; rules_count={1}; llm.provider={2}" -f $json.status,$json.rules_count,$json.llm.provider)
    } else {
      OK "Health 200 (raw body received)"
    }
    INF ("Endpoint: {0} | Listening: {1}:{2}" -f $healthUrl,$hostip,$port)
  } else {
    ERR ("Health failed via curl (exit={0})" -f $LASTEXITCODE)
    Pop-Location; exit 45
  }
}
else {
  # 2) Fallback: Invoke-WebRequest with TLS12 and Connection: close
  [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
  [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
  try{
    $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 6 -Headers @{ Connection = 'close' }
    $json=$null; try{ $json = $r.Content | ConvertFrom-Json -ErrorAction Stop } catch {}
    if($json){
      OK ("Health {0}: status={1}; rules_count={2}; llm.provider={3}" -f $r.StatusCode,$json.status,$json.rules_count,$json.llm.provider)
    } else {
      OK ("Health {0}" -f $r.StatusCode)
    }
    INF ("Endpoint: {0} | Listening: {1}:{2}" -f $healthUrl,$hostip,$port)
  } catch {
    ERR ("Health failed: {0}" -f $_.Exception.Message)
    Pop-Location; exit 45
  }
}


# desktop shortcut (optional)
if($InstallShortcut){
  try{
    $bat = Join-Path $Root "ContractAI-Start.bat"
    $desktop=[Environment]::GetFolderPath('Desktop')
    $lnk = Join-Path $desktop "ContractAI - Start.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($lnk)
    $sc.TargetPath = $bat
    $sc.WorkingDirectory = $Root
    $sc.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    $sc.Save()
    OK ("Shortcut: {0}" -f $lnk)
  } catch { WRN ("Shortcut failed: {0}" -f $_.Exception.Message) }
}

Pop-Location
OK "Done"
exit 0
