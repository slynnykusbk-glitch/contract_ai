# tools/full_doctor.ps1  (PS 5.1 compatible)
param(
  [switch]$SkipNpm,
  [switch]$SkipApi,
  [switch]$SkipPreCommit
)

$ErrorActionPreference = 'Stop'
$stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
$logPath = Join-Path $PSScriptRoot "..\doctor_report_$stamp.log"
$summaryPath = Join-Path $PSScriptRoot "..\doctor_summary_$stamp.json"

# ordered summary object for JSON
$summary = [ordered]@{
  startedAt = (Get-Date).ToString('s')
  steps     = @()
}

function Write-Log([string]$msg) {
  $line = $msg -replace "`r?`n$",""
  Add-Content -LiteralPath $logPath -Encoding UTF8 -Value $line
}

function Add-Step([string]$name, [bool]$ok, [string[]]$details) {
  $summary.steps += [ordered]@{ name=$name; ok=$ok; details=($details | Where-Object { $_ -ne $null }) }
}

function Exec($file, [string[]]$args) {
  $argsJoined = if ($args) { ($args -join ' ') } else { '' }
  Write-Log "`n=== $file $argsJoined ==="

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName               = $file
  $psi.Arguments              = $argsJoined
  $psi.UseShellExecute        = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi

  try {
    [void]$p.Start()
  } catch {
    Write-Log "[EXE] $($_.Exception.Message)"
    return @{ code=9001; out=''; err=$_.Exception.Message }
  }

  $out = $p.StandardOutput.ReadToEnd()
  $err = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($out) { Write-Log $out }
  if ($err) { Write-Log $err }
  return @{ code=$p.ExitCode; out=$out; err=$err }
}

# ---------- 1) Git status ----------
try {
  Write-Log "=== Git status ==="
  $b = Exec 'git' @('rev-parse','--abbrev-ref','HEAD')
  $s = Exec 'git' @('status','--porcelain')
  $l = Exec 'git' @('log','-1','--oneline')

  Write-Log ("Branch: " + ($b.out.Trim()))
  if ($s.out) { Write-Log ("Dirty files:`n" + $s.out.Trim()) } else { Write-Log "Dirty files:" }
  Write-Log ("Last commit:`n" + $l.out.Trim())

  Add-Step "Git status" $true @()
} catch {
  Add-Step "Git status" $false @($_.Exception.Message)
}

# ---------- 2) Merge markers ----------
try {
  Write-Log "`n=== Merge markers ==="
  # точные маркеры конфликтов
  $mm1 = Exec 'git' @('grep','-n','-E','^<<<<<<< ','--','.')
  $mm2 = Exec 'git' @('grep','-n','-E','^=======$','--','.')
  $mm3 = Exec 'git' @('grep','-n','-E','^>>>>>>> ','--','.')

  $hits = @()
  if ($mm1.out) { $hits += $mm1.out.Trim().Split("`n") }
  if ($mm2.out) { $hits += $mm2.out.Trim().Split("`n") }
  if ($mm3.out) { $hits += $mm3.out.Trim().Split("`n") }

  if ($hits.Count -gt 0) {
    $preview = ($hits | Select-Object -First 30)
    $preview | ForEach-Object { Write-Log $_ }
    Add-Step "Merge markers" $false @("Merge markers found", "Samples:", ($preview -join '; '))
  } else {
    Add-Step "Merge markers" $true @()
  }
} catch {
  Add-Step "Merge markers" $false @($_.Exception.Message)
}

# ---------- 3) Pattern scan ----------
try {
  Write-Log "`n=== Pattern scan: legacy imports / bad API usage ==="
  $warns = @()

  $raw = Exec 'git' @('grep','-n','-E','body\.search\(','--','*.ts')
  if ($raw.out) { $warns += "raw body.search found:"; Write-Log $raw.out }

  $loads = Exec 'git' @('grep','-n','-E','\.load\(''items''\)','--','*.ts')
  if ($loads.out) { $warns += "load('items') in taskpane.ts:"; Write-Log $loads.out }

  if ($warns.Count -gt 0) {
    Add-Step "Pattern scan: legacy imports / bad API usage" $true @()
  } else {
    Add-Step "Pattern scan: legacy imports / bad API usage" $true @()
  }
} catch {
  Add-Step "Pattern scan: legacy imports / bad API usage" $false @($_.Exception.Message)
}

# ---------- 4) Tools ----------
try {
  Write-Log "`n=== Tools: node/npm/pre-commit ==="
  $n  = Exec 'node' @('--version')
  $np = Exec 'npm'  @('--version')
  Write-Log ("node: " + $n.out.Trim())
  Write-Log ("npm: "  + $np.out.Trim())

  if (-not $SkipPreCommit) {
    $pc = Exec 'pre-commit' @('--version')
    if ($pc.code -eq 9001) { Write-Log "[WARN] pre-commit not found" }
  }

  Add-Step "Tools: node/npm/pre-commit" $true @()
} catch {
  Add-Step "Tools: node/npm/pre-commit" $false @($_.Exception.Message)
}

# ---------- 5) AOAI / env ----------
try {
  Write-Log "`n=== AOAI / env ==="
  $prov   = $env:LLM_PROVIDER
  $ep     = $env:AZURE_OPENAI_ENDPOINT
  $ver    = $env:AZURE_OPENAI_API_VERSION
  $dep    = $env:AZURE_OPENAI_DEPLOYMENT
  $schema = if ($env:SCHEMA_VERSION) { $env:SCHEMA_VERSION } else { '1.4' }

  Write-Log ("LLM_PROVIDER=$prov")
  Write-Log ("AZURE_OPENAI_ENDPOINT=$ep")
  Write-Log ("AZURE_OPENAI_API_VERSION=$ver")
  Write-Log ("AZURE_OPENAI_DEPLOYMENT=$dep")
  Write-Log ("AZURE_OPENAI_API_KEY=" + ('*' * 84))
  Write-Log ("SCHEMA_VERSION=$schema")

  if ($prov -eq 'azure' -and ($ep -notmatch 'azure\.com')) {
    Write-Log "[WARN] bad AZURE_OPENAI_ENDPOINT"
    Add-Step "AOAI / env" $true @("bad AZURE_OPENAI_ENDPOINT")
  } else {
    Add-Step "AOAI / env" $true @()
  }
} catch {
  Add-Step "AOAI / env" $false @($_.Exception.Message)
}

# ---------- 6) npm ci / build ----------
if (-not $SkipNpm) {
  try {
    Write-Log "`n=== npm ci (panel) ==="
    $ci = Exec 'npm' @('--prefix','word_addin_dev','ci')
    if ($ci.code -ne 0) { throw "npm ci failed (exit $($ci.code))" }
    Add-Step "npm ci (panel)" $true @()
  } catch {
    Add-Step "npm ci (panel)" $false @($_.Exception.Message)
  }

  try {
    Write-Log "`n=== vite build (panel) ==="
    $b = Exec 'npm' @('--prefix','word_addin_dev','run','build')
    if ($b.code -ne 0) { throw "vite build failed (exit $($b.code))" }
    Add-Step "vite build (panel)" $true @()
  } catch {
    Add-Step "vite build (panel)" $false @($_.Exception.Message)
  }
}

# ---------- 7) API smoke ----------
if (-not $SkipApi) {
  try {
    Write-Log "`n=== API health ==="
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    $null = [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

    $apiKey   = if ($env:API_KEY) { $env:API_KEY } else { 'local-test-key-123' }
    $schemaH  = if ($env:SCHEMA_VERSION) { $env:SCHEMA_VERSION } else { '1.4' }
    $headers  = @{ 'X-Api-Key' = $apiKey; 'X-Schema-Version' = $schemaH }

    $h = Invoke-WebRequest -Uri 'https://localhost:9443/api/health' -Headers $headers -UseBasicParsing -TimeoutSec 10
    Write-Log ($h.StatusCode.ToString() + " " + $h.Content)
    Add-Step "API health" $true @()
  } catch {
    Add-Step "API health" $false @($_.Exception.Message)
  }

  try {
    Write-Log "`n=== API analyze (smoke) ==="
    $body = @{ mode='live'; text='Hello. This is a tiny test.' } | ConvertTo-Json -Compress
    $a = Invoke-WebRequest -Uri 'https://localhost:9443/api/analyze' -Headers $headers -UseBasicParsing -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 30
    Write-Log ($a.StatusCode.ToString() + " " + ($a.Content.Substring(0,[Math]::Min(400,$a.Content.Length))))
    Add-Step "API analyze (smoke)" $true @()
  } catch {
    Add-Step "API analyze (smoke)" $false @($_.Exception.Message)
  }

  try {
    Write-Log "`n=== API draft (smoke) ==="
    $body2 = @{ text='Example clause'; mode='friendly' } | ConvertTo-Json -Compress
    $d = Invoke-WebRequest -Uri 'https://localhost:9443/api/draft' -Headers $headers -UseBasicParsing -Method Post -ContentType 'application/json' -Body $body2 -TimeoutSec 30
    Write-Log ($d.StatusCode.ToString() + " " + ($d.Content.Substring(0,[Math]::Min(400,$d.Content.Length))))
    Add-Step "API draft (smoke)" $true @()
  } catch {
    Add-Step "API draft (smoke)" $false @($_.Exception.Message)
  }
}

# ---------- 8) pre-commit ----------
if (-not $SkipPreCommit) {
  try {
    Write-Log "`n=== pre-commit run --all-files ==="
    $pcall = Exec 'pre-commit' @('run','--all-files')
    if ($pcall.code -ne 0) { throw "pre-commit failed (exit $($pcall.code))" }
    Add-Step "pre-commit run --all-files" $true @()
  } catch {
    Add-Step "pre-commit run --all-files" $false @($_.Exception.Message)
  }
}

$summary.endedAt = (Get-Date).ToString('s')
$summary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $summaryPath

Write-Host ("`nReport: " + (Split-Path -Leaf $logPath))
Write-Host ("Summary: " + (Split-Path -Leaf $summaryPath))
