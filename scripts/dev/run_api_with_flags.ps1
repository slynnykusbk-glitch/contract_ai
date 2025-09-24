[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function OK($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function INF($m){ Write-Host "[INF] $m" -ForegroundColor Cyan }
function WRN($m){ Write-Host "[WRN] $m" -ForegroundColor Yellow }
function ERR($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = (Resolve-Path (Join-Path $ScriptDir '..' '..')).Path
Push-Location $Root

try {
  $flags = [ordered]@{
    'FEATURE_TRACE_ARTIFACTS' = '1'
    'FEATURE_REASON_OFFSETS'  = '1'
    'FEATURE_COVERAGE_MAP'    = '1'
    'FEATURE_AGENDA_SORT'     = '1'
    'FEATURE_AGENDA_STRICT_MERGE' = '0'
  }

  foreach($entry in $flags.GetEnumerator()){
    Set-Item -Path "env:$($entry.Key)" -Value $entry.Value
  }
  $flagLine = ($flags.GetEnumerator() | ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }) -join ' '
  Write-Host ("[run_api_with_flags] Flags: {0}" -f $flagLine)

  $py = if(Test-Path ".venv\Scripts\python.exe"){ ".\.venv\Scripts\python.exe" }
        elseif(Test-Path "venv\Scripts\python.exe"){ ".\venv\Scripts\python.exe" } else { "python" }
  $crt = Join-Path $Root "dev\localhost.crt"
  $keyf = Join-Path $Root "dev\localhost.key"
  if(-not (Test-Path $crt) -or -not (Test-Path $keyf)){
    ERR ("Missing TLS files: {0} ; {1}" -f $crt,$keyf)
    exit 43
  }

  $hostip = '127.0.0.1'
  $port   = 9443

  $listen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if($listen){
    WRN ("Port {0} already listening (PID={1}); skipping spawn" -f $port,$listen.OwningProcess)
    return
  }

  INF "Ensuring Python dependencies (requirements.txt)..."
  & $py -m pip install -r requirements.txt | Out-Null

  $args = @('-m','uvicorn','contract_review_app.api.app:app','--host',$hostip,'--port',$port,'--ssl-certfile',$crt,'--ssl-keyfile',$keyf)
  INF ("Start: {0} {1}" -f $py, ($args -join ' '))
  $proc = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $Root -PassThru
  OK  ("Uvicorn PID={0}" -f $proc.Id)

  $deadline=(Get-Date).AddSeconds(25)
  do{
    Start-Sleep -Milliseconds 500
    $listen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  } until($listen -or (Get-Date) -ge $deadline)
  if(-not $listen){
    ERR ("Port {0} did not open in time" -f $port)
    exit 44
  }

  $healthUrl = ('https://{0}:{1}/health' -f $hostip,$port)
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
      exit 45
    }
  }
  else {
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
      exit 45
    }
  }
}
finally {
  Pop-Location
}
exit 0
