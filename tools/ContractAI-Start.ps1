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

INF "Rebuilding panel via scripts/dev/rebuild_panel.ps1..."
$rebuildScript = Join-Path $Root 'scripts/dev/rebuild_panel.ps1'
& $rebuildScript
if ($LASTEXITCODE -ne 0) {
  ERR ("Panel rebuild failed with exit code {0}" -f $LASTEXITCODE)
  Pop-Location; exit $LASTEXITCODE
}

INF "Starting backend via scripts/dev/run_api_with_flags.ps1..."
$apiScript = Join-Path $Root 'scripts/dev/run_api_with_flags.ps1'
& $apiScript
$apiExit = $LASTEXITCODE
if ($apiExit -ne 0) {
  ERR ("Backend launcher exited with code {0}" -f $apiExit)
  Pop-Location; exit $apiExit
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
