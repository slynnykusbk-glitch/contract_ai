param(
  [string]$Repo = (Resolve-Path "$PSScriptRoot\.." ).Path,
  [string]$Name = 'Contract AI (Dev)',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Convert-PngToIco {
  param(
    [string]$PngPath,
    [string]$IcoPath
  )
  if (-not (Test-Path $PngPath)) {
    return $false
  }
  try {
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
  } catch {
    Write-Warning "System.Drawing not available: $_"
    return $false
  }
  try {
    Add-Type -Namespace Win32 -Name NativeMethods -MemberDefinition '[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool DestroyIcon(System.IntPtr handle);' -ErrorAction SilentlyContinue | Out-Null
  } catch {
    # ignore if already loaded
  }
  try {
    $bitmap = [System.Drawing.Bitmap]::new($PngPath)
    try {
      $iconHandle = $bitmap.GetHicon()
      $icon = [System.Drawing.Icon]::FromHandle($iconHandle)
      try {
        $stream = [System.IO.File]::Create($IcoPath)
        try {
          $icon.Save($stream)
        } finally {
          $stream.Dispose()
        }
      } finally {
        $icon.Dispose()
        if ([type]::GetType('Win32.NativeMethods')) {
          [Win32.NativeMethods]::DestroyIcon($iconHandle) | Out-Null
        }
      }
    } finally {
      $bitmap.Dispose()
    }
    return $true
  } catch {
    Write-Warning "Unable to create icon: $_"
    return $false
  }
}

$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) {
  throw 'Unable to resolve Desktop path.'
}

$shortcutPath = Join-Path $desktop ("$Name.lnk")
if (Test-Path $shortcutPath) {
  if (-not $Force) {
    Write-Host "Shortcut already exists: $shortcutPath" -ForegroundColor Yellow
    return
  }
  Remove-Item -LiteralPath $shortcutPath -Force
}

$targetBat = Join-Path $Repo 'ContractAI-Start.bat'
if (-not (Test-Path $targetBat)) {
  throw "ContractAI-Start.bat not found at $targetBat"
}

$iconLocation = 'shell32.dll,167'
$iconPng = Join-Path $Repo 'word_addin_dev\app\assets\icon-32.png'
$iconIco = Join-Path $Repo 'word_addin_dev\app\assets\icon-32.ico'
if (Test-Path $iconPng) {
  $needRebuild = $true
  if (Test-Path $iconIco) {
    try {
      $pngTime = (Get-Item -LiteralPath $iconPng).LastWriteTimeUtc
      $icoTime = (Get-Item -LiteralPath $iconIco).LastWriteTimeUtc
      $needRebuild = $pngTime -gt $icoTime
    } catch {
      $needRebuild = $true
    }
  }
  if ($needRebuild) {
    if (-not (Convert-PngToIco -PngPath $iconPng -IcoPath $iconIco)) {
      $iconIco = $null
    }
  }
  if ($iconIco -and (Test-Path $iconIco)) {
    $iconLocation = $iconIco
  }
}

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $Repo
$shortcut.WindowStyle = 1
$shortcut.IconLocation = $iconLocation
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
