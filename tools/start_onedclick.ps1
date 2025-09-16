param(
  [switch]$CreateShortcut,
  [switch]$SkipBrowser
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
  Write-Warning "Unable to enforce TLS 1.2: $_"
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
Set-Location $repo

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Stop-ProcessSafe {
  param([string[]]$Names)
  foreach ($name in $Names) {
    try {
      Get-Process -Name $name -ErrorAction Stop | ForEach-Object {
        Write-Host "Stopping $name (PID=$($_.Id))" -ForegroundColor Yellow
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
      }
    } catch {
      # process not running – ignore
    }
  }
}

function Get-ManifestId {
  param([string]$ManifestPath)
  try {
    $xml = [xml](Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8)
    return [string]$xml.OfficeApp.Id
  } catch {
    Write-Warning "Unable to read manifest ID: $_"
    return $null
  }
}

function Clear-StaleGuidFolders {
  param(
    [string]$BasePath,
    [string]$Guid,
    [string]$Label
  )
  if ([string]::IsNullOrWhiteSpace($BasePath) -or -not (Test-Path $BasePath)) {
    return $false
  }
  if ([string]::IsNullOrWhiteSpace($Guid)) {
    return $false
  }

  $current = Join-Path $BasePath $Guid
  if (Test-Path $current) {
    Write-Host "$Label cache is up-to-date ($Guid)" -ForegroundColor DarkGreen
    return $false
  }

  $removed = $false
  $guidPattern = '^[0-9a-fA-F-]{36}$'
  Get-ChildItem -Path $BasePath -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -match $guidPattern -and $_.Name -ne $Guid) {
      Write-Host "Removing stale $Label cache: $($_.FullName)" -ForegroundColor Yellow
      Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      $removed = $true
    }
  }
  return $removed
}

function Get-PythonCommand {
  param([string]$RepoPath)
  $candidates = @(
    @{ File = (Join-Path $RepoPath '.venv\Scripts\python.exe'); Args = @() },
    @{ File = (Join-Path $RepoPath 'venv\Scripts\python.exe');  Args = @() },
    @{ File = 'py';       Args = @('-3') },
    @{ File = 'python';   Args = @() }
  )
  foreach ($candidate in $candidates) {
    $file = $candidate.File
    $args = $candidate.Args
    if ($file -like '*python.exe') {
      if (Test-Path $file) { return $candidate }
      continue
    }
    try {
      $null = Get-Command $file -ErrorAction Stop
      return $candidate
    } catch {
      continue
    }
  }
  throw 'Python interpreter not found. Activate your virtual environment or install Python.'
}

function Invoke-Python {
  param(
    [hashtable]$Python,
    [string[]]$Args
  )
  & $Python.File @($Python.Args + $Args)
}

function Ensure-DevCertificate {
  param(
    [string]$CertPath,
    [string]$KeyPath,
    [hashtable]$Python
  )
  $result = [ordered]@{
    CertExists   = (Test-Path $CertPath)
    KeyExists    = (Test-Path $KeyPath)
    Generated    = $false
    Imported     = $false
    Thumbprint   = $null
  }

  if (-not $result.CertExists -or -not $result.KeyExists) {
    Write-Host 'Generating development certificate...' -ForegroundColor Yellow
    Invoke-Python $Python @((Join-Path $repo 'gen_cert.py'))
    $result.Generated = $true
    $result.CertExists = Test-Path $CertPath
    $result.KeyExists = Test-Path $KeyPath
  }

  if (-not $result.CertExists -or -not $result.KeyExists) {
    throw "Development certificate was not created: $CertPath / $KeyPath"
  }

  try {
    $certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $CertPath
    $result.Thumbprint = $certObj.Thumbprint
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root','CurrentUser')
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    try {
      $exists = $false
      foreach ($c in $store.Certificates) {
        if ($c.Thumbprint -eq $certObj.Thumbprint) {
          $exists = $true
          break
        }
      }
      if (-not $exists) {
        $store.Add($certObj)
        $result.Imported = $true
        Write-Host "Imported dev certificate into CurrentUser\\Root (Thumbprint=$($certObj.Thumbprint))" -ForegroundColor Green
      } else {
        Write-Host "Dev certificate already trusted (Thumbprint=$($certObj.Thumbprint))" -ForegroundColor DarkGreen
      }
    } finally {
      $store.Close()
    }
  } catch {
    Write-Warning "Failed to import certificate: $_"
  }

  return $result
}

function Ensure-Manifest {
  param(
    [string]$Source,
    [string]$DestinationDir
  )
  if (-not (Test-Path $Source)) {
    throw "Manifest not found: $Source"
  }
  New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null
  $destination = Join-Path $DestinationDir 'manifest.xml'
  $needsCopy = -not (Test-Path $destination)
  if (-not $needsCopy) {
    try {
      $srcHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash
      $dstHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash
      $needsCopy = $srcHash -ne $dstHash
    } catch {
      $needsCopy = $true
    }
  }
  if ($needsCopy) {
    Copy-Item -LiteralPath $Source -Destination $destination -Force
    Write-Host "Manifest copied to $destination" -ForegroundColor Green
  } else {
    Write-Host "Manifest already up-to-date at $destination" -ForegroundColor DarkGreen
  }
  return @{ Path = $destination; Updated = $needsCopy }
}

function Invoke-StatusCheck {
  param(
    [string]$Url,
    [int]$TimeoutSec = 20,
    [System.Diagnostics.Process]$Process = $null
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  $lastError = $null
  while ((Get-Date) -lt $deadline) {
    if ($Process -and $Process.HasExited) {
      return @{ Success = $false; Error = "Process exited with code $($Process.ExitCode)" }
    }
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -eq 200) {
        return @{ Success = $true; Error = $null }
      }
      $lastError = "Status $($response.StatusCode)"
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Milliseconds 700
  }
  return @{ Success = $false; Error = $lastError }
}

# ---------------------------------------------------------------------
# 0) Optional desktop shortcut
if ($CreateShortcut) {
  Write-Step 'Creating desktop shortcut'
  & (Join-Path $root 'create_desktop_shortcut.ps1') -Repo $repo -Force
}

# ---------------------------------------------------------------------
# 1) Stop conflicting processes and refresh caches
Write-Step 'Stopping Word and WebView2 processes'
Stop-ProcessSafe -Names @('WINWORD','msedgewebview2','MicrosoftEdgeWebView2','MicrosoftEdgeWebview2','WebViewHost')

$manifestPath = Join-Path $repo 'word_addin_dev\manifest.xml'
$manifestId = Get-ManifestId -ManifestPath $manifestPath
if ($manifestId) {
  Write-Step "Validating Office cache for manifest $manifestId"
  $wefBase = Join-Path $env:LOCALAPPDATA 'Microsoft\Office\16.0\WEF\AddinInfo\1\filesystem\Word\1'
  $webViewBase = Join-Path $env:LOCALAPPDATA 'Microsoft\Office\16.0\WEF\WebViewCache\Word\1'
  Clear-StaleGuidFolders -BasePath $wefBase -Guid $manifestId -Label 'WEF' | Out-Null
  Clear-StaleGuidFolders -BasePath $webViewBase -Guid $manifestId -Label 'WebView2' | Out-Null
}

# ---------------------------------------------------------------------
# 2) Ensure certificates
Write-Step 'Ensuring development TLS certificates'
$loopbackLabel = 'local' + 'host'
$crtPath = Join-Path $repo ("dev\{0}.crt" -f $loopbackLabel)
$keyPath = Join-Path $repo ("dev\{0}.key" -f $loopbackLabel)
$pythonCmd = Get-PythonCommand -RepoPath $repo
$certInfo = Ensure-DevCertificate -CertPath $crtPath -KeyPath $keyPath -Python $pythonCmd
$certLoaded = $certInfo.CertExists -and $certInfo.KeyExists

# ---------------------------------------------------------------------
# 3) Ensure manifest copy in shared catalog
Write-Step 'Syncing manifest to shared catalog'
$userProfile = [Environment]::GetFolderPath('UserProfile')
if (-not $userProfile) {
  $userProfile = $env:USERPROFILE
}
if (-not $userProfile) {
  $homeDrive = [Environment]::GetEnvironmentVariable('HOMEDRIVE')
  $homePath = [Environment]::GetEnvironmentVariable('HOMEPATH')
  if ($homeDrive -and $homePath) {
    $userProfile = Join-Path $homeDrive $homePath.TrimStart('\','/')
  }
}
if (-not $userProfile) {
  throw 'Unable to resolve USERPROFILE path.'
}
$catalogDir = Join-Path $userProfile 'contract_ai\_shared_catalog'
$manifestSync = Ensure-Manifest -Source $manifestPath -DestinationDir $catalogDir

$origin = 'https://127.0.0.1:9443'
$healthUrl = "$origin/health"
$catalogUrl = "$origin/catalog/manifest.xml"
$panelUrl = "$origin/panel/taskpane.html"

# ---------------------------------------------------------------------
# 4) Start uvicorn
Write-Step 'Starting uvicorn (https://127.0.0.1:9443)'
$uvicornArgs = @($pythonCmd.Args + @(
    '-m','uvicorn','contract_review_app.api.app:app',
    '--host','127.0.0.1',
    '--port','9443',
    '--ssl-certfile',$crtPath,
    '--ssl-keyfile',$keyPath
))
$uvicornProcess = Start-Process -FilePath $pythonCmd.File -ArgumentList $uvicornArgs -WorkingDirectory $repo -NoNewWindow -PassThru
Start-Sleep -Seconds 1
if ($uvicornProcess.HasExited) {
  throw "uvicorn failed to start (ExitCode=$($uvicornProcess.ExitCode))"
}
$exitHandler = Register-EngineEvent PowerShell.Exiting -Action {
  param($sender,$eventArgs)
  if ($uvicornProcess -and -not $uvicornProcess.HasExited) {
    try { $uvicornProcess.CloseMainWindow() | Out-Null } catch {}
    Start-Sleep -Milliseconds 200
    if (-not $uvicornProcess.HasExited) {
      try { $uvicornProcess.Kill() | Out-Null } catch {}
    }
  }
} 

# ---------------------------------------------------------------------
# 5) Health checks
Write-Step 'Waiting for health endpoint'
$healthResult = Invoke-StatusCheck -Url $healthUrl -TimeoutSec 30 -Process $uvicornProcess
$healthOk = $healthResult.Success
if (-not $healthOk) {
  Write-Warning "Health check failed: $($healthResult.Error)"
}

$catalogResult = @{ Success = $false; Error = $null }
$panelResult = @{ Success = $false; Error = $null }
if ($healthOk) {
  $catalogResult = Invoke-StatusCheck -Url $catalogUrl -TimeoutSec 15 -Process $uvicornProcess
  if (-not $catalogResult.Success) {
    Write-Warning "Catalog check failed: $($catalogResult.Error)"
  }
  $panelResult = Invoke-StatusCheck -Url $panelUrl -TimeoutSec 15 -Process $uvicornProcess
  if (-not $panelResult.Success) {
    Write-Warning "Panel check failed: $($panelResult.Error)"
  }
} else {
  Write-Warning 'Skipping catalog/panel checks because health did not return 200.'
}

$catalogOk = $catalogResult.Success
$panelOk = $panelResult.Success

# ---------------------------------------------------------------------
# 6) Summary and optional browser launch
$checks = @(
  @{ Label = 'cert loaded'; Success = $certLoaded },
  @{ Label = 'health 200'; Success = $healthOk },
  @{ Label = 'catalog 200'; Success = $catalogOk },
  @{ Label = 'panel 200'; Success = $panelOk }
)
$summary = $checks | ForEach-Object {
  if ($_.Success) { "✔ $($_.Label)" } else { "✖ $($_.Label)" }
}
$allGreen = $checks | Where-Object { -not $_.Success } | Measure-Object | Select-Object -ExpandProperty Count
if ($allGreen -eq 0) {
  Write-Host ''
  Write-Host ($summary -join ', ') -ForegroundColor Green
} else {
  Write-Host ''
  Write-Host ($summary -join ', ') -ForegroundColor Yellow
}

if (-not $SkipBrowser -and $panelOk) {
  Write-Step 'Opening taskpane in default browser'
  Start-Process "$panelUrl?v=dev"
}

Write-Host ''
Write-Host "uvicorn PID: $($uvicornProcess.Id). Press Ctrl+C to stop." -ForegroundColor Cyan
try {
  Wait-Process -Id $uvicornProcess.Id
} finally {
  if ($exitHandler) {
    Unregister-Event -SubscriptionId $exitHandler.Id
  }
  if ($uvicornProcess -and -not $uvicornProcess.HasExited) {
    try { $uvicornProcess.CloseMainWindow() | Out-Null } catch {}
    Start-Sleep -Milliseconds 200
    if (-not $uvicornProcess.HasExited) {
      try { $uvicornProcess.Kill() | Out-Null } catch {}
    }
  }
}
