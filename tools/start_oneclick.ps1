#requires -version 5.1
# This script starts the ContractAI backend and optionally sideloads the
# Word add-in. Elevation is only required for certificate generation tasks;
# Word should be launched in the intended user's context.
[CmdletBinding()]
param(
    [switch]$OpenWord,
    [switch]$CreateShortcut
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logFile = Join-Path $env:TEMP 'ContractAI-oneclick.log'
function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    try { "$ts $Message" | Out-File -FilePath $logFile -Append -Encoding UTF8 } catch {}
}

function Load-DotEnv {
    param([string]$Path)
    if (!(Test-Path $Path)) { Write-Log "[WARN] .env not found"; return }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*$' -or $line -match '^\s*#') { continue }
        $parts = $line -split '=',2
        if ($parts.Count -ne 2) { continue }
        $k = $parts[0].Trim()
        $v = $parts[1].Trim()
        $cur = [System.Environment]::GetEnvironmentVariable($k, "Process")
        if ([string]::IsNullOrEmpty($cur)) {
            [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
        }
    }
    Write-Log '[OK] .env loaded'
}

function Ensure-Certs {
    $cert = Join-Path $repo 'word_addin_dev\certs\localhost.pem'
    $key  = Join-Path $repo 'word_addin_dev\certs\localhost-key.pem'
    if (!(Test-Path $cert) -or !(Test-Path $key)) {
        Write-Log '[INFO] generating dev certs'
        & "$repo\.venv\Scripts\python.exe" "$repo\word_addin_dev\gen_dev_certs.py" | Out-Null
    }
    return @{cert=$cert; key=$key}
}

function Start-Backend {
    param([string]$Cert, [string]$Key)
    $py = Join-Path $repo '.venv\Scripts\python.exe'
    $args = @('-m','uvicorn','contract_review_app.api.app:app','--host','localhost','--port','9443',
              '--ssl-certfile',$Cert,'--ssl-keyfile',$Key)
    Start-Process -FilePath $py -ArgumentList $args -WindowStyle Minimized -WorkingDirectory $repo | Out-Null
    Write-Log '[OK] backend started'
}

function Wait-BackendHealth {
    param(
        [string]$Url = 'https://localhost:9443/health',
        [int]$TimeoutSeconds = 30
    )
    for ($i=0; $i -lt $TimeoutSeconds; $i++) {
        try {
            $tcp = Test-NetConnection -ComputerName 'localhost' -Port 9443 -WarningAction SilentlyContinue
            if ($tcp.TcpTestSucceeded) {
                $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 -SkipCertificateCheck
                if ($r.StatusCode -eq 200) { return $true }
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

function Open-Panel {
    Start-Process 'https://localhost:9443/panel/panel_selftest.html?v=dev'
    Write-Log '[OK] panel opened'
}

function Sideload-Word {
    param(
        [string]$UserProfile
    )
    $src = Join-Path $repo 'word_addin_dev\manifest.xml'
    # If no profile is specified, attempt to locate the non-elevated user via HKU.
    if (-not $UserProfile) {
        try {
            $sid = (Get-ChildItem 'HKU:' | Where-Object { $_.Name -match '^HKEY_USERS\\S-1-5-21' } | Select-Object -First 1).PSChildName
            if ($sid) {
                $UserProfile = (Get-ItemProperty -Path "Registry::HKU\$sid\Volatile Environment" -ErrorAction Stop).USERPROFILE
            }
        } catch {}
        if (-not $UserProfile) { $UserProfile = $env:USERPROFILE }
    }
    $dst = Join-Path $UserProfile 'AppData\Local\Microsoft\Office\16.0\Wef'
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Copy-Item $src (Join-Path $dst 'manifest.xml') -Force
    Start-Process -FilePath 'WINWORD.EXE' | Out-Null
    Write-Log '[OK] Word launched'
}

function Create-Shortcut {
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $lnk = Join-Path $desktop 'Contract AI — Start.lnk'
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath = Join-Path $repo 'ContractAI-Start.bat'
    $sc.WorkingDirectory = $repo
    $sc.Save()
    Write-Log '[OK] shortcut created'
}

function Start-OneClick {
    Write-Log '[INFO] starting oneclick'
    $act = Join-Path $repo '.venv\Scripts\Activate.ps1'
    if (Test-Path $act) { . $act }
    Load-DotEnv (Join-Path $repo '.env')
    $c = Ensure-Certs
    Start-Backend -Cert $c.cert -Key $c.key
    if (Wait-BackendHealth) {
        Write-Log '[OK] health ready'
        Open-Panel
        if ($OpenWord) { Sideload-Word }
        if ($CreateShortcut) { Create-Shortcut }
    } else {
        Write-Log '[ERR] health timeout'
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Start-OneClick
}
