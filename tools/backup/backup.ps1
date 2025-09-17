[CmdletBinding()]
param(
    [string]$Label,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = [System.IO.Path]::TrimEndingDirectorySeparator((Resolve-Path -Path (Join-Path $scriptDir '..\..')).Path)
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

Write-Host "Repository root: $repoRoot"
if ($Label) {
    Write-Host "Requested label: $Label"
}
if ($DryRun) {
    Write-Host "Running in dry-run mode."
}

# Run secret scan before proceeding
$scanScript = Join-Path $scriptDir 'scan_secrets.ps1'
if (-not (Test-Path -LiteralPath $scanScript)) {
    throw "Secret scan script not found at $scanScript"
}

& pwsh -NoLogo -NoProfile -File $scanScript
$scanExitCode = $LASTEXITCODE
if ($scanExitCode -eq 2) {
    Write-Error "Secret patterns detected. Backup aborted."
    exit 2
} elseif ($scanExitCode -ne 0) {
    Write-Error "Secret scan failed with exit code $scanExitCode."
    exit $scanExitCode
}

$excludeFile = Join-Path $scriptDir '.backup-exclude.txt'
if (-not (Test-Path -LiteralPath $excludeFile)) {
    throw "Exclude file not found at $excludeFile"
}

function Convert-PatternToRegex {
    param(
        [string]$Pattern
    )
    $normalized = $Pattern.Trim()
    $normalized = $normalized -replace '\\', '/'
    $normalized = $normalized.TrimStart('/')
    if ($normalized.Length -eq 0) {
        return '^$'
    }
    $escaped = [regex]::Escape($normalized)
    $escaped = $escaped -replace '\\\*\\\*', '.*'
    $escaped = $escaped -replace '\\\*', '[^/]*'
    $escaped = $escaped -replace '\\\?', '[^/]'
    return '^' + $escaped + '$'
}

$excludePatterns = @()
Get-Content -LiteralPath $excludeFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $regexPattern = Convert-PatternToRegex -Pattern $line
    $excludePatterns += [pscustomobject]@{
        Pattern = $line
        Regex   = [regex]::new($regexPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }
}

$repoRootWithSep = [System.IO.Path]::TrimEndingDirectorySeparator($repoRoot)

$allFiles = Get-ChildItem -Path $repoRoot -File -Recurse
$included = @()
$excluded = @()

foreach ($file in $allFiles) {
    $relative = $file.FullName.Substring($repoRootWithSep.Length)
    $relative = $relative.TrimStart([char]'\', [char]'/' )
    $relativeNormalized = $relative -replace '\\', '/'
    $matchedPattern = $null
    foreach ($entry in $excludePatterns) {
        if ($entry.Regex.IsMatch($relativeNormalized)) {
            $matchedPattern = $entry.Pattern
            break
        }
    }
    if ($matchedPattern) {
        $excluded += [pscustomobject]@{
            Path    = $relativeNormalized
            Pattern = $matchedPattern
        }
        continue
    }
    $included += [pscustomobject]@{
        Path     = $relativeNormalized
        FullName = $file.FullName
        Size     = $file.Length
    }
}

Write-Host "Total files discovered: $($allFiles.Count)"
Write-Host "Included files: $($included.Count)"
Write-Host "Excluded files: $($excluded.Count)"

if ($DryRun) {
    Write-Host "--- Included ---"
    foreach ($item in $included | Sort-Object Path) {
        Write-Host "  $($item.Path)"
    }
    Write-Host "--- Excluded ---"
    foreach ($item in $excluded | Sort-Object Path) {
        Write-Host "  $($item.Path) (pattern: $($item.Pattern))"
    }
    Write-Host "Dry run complete. No archive or manifest created."
    exit 0
}

if ($included.Count -eq 0) {
    Write-Warning "No files to include in backup."
    exit 0
}

$safeLabel = $null
if ($Label) {
    $safeLabel = ($Label -replace '[^A-Za-z0-9_\-]+', '_').Trim('_')
}

$archiveBaseName = "backup_$timestamp"
if ($safeLabel) {
    $archiveBaseName += "_" + $safeLabel
}

$backupDir = Join-Path $repoRoot '_backups'
$archivePath = Join-Path $backupDir ($archiveBaseName + '.zip')
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$includedPaths = $included | ForEach-Object { $_.Path }

Push-Location -Path $repoRoot
try {
    Compress-Archive -Path $includedPaths -DestinationPath $archivePath -CompressionLevel Optimal -Force
} finally {
    Pop-Location
}

Write-Host "Archive created at: $archivePath"

$manifestDir = Join-Path $repoRoot 'reports/backups'
New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
$manifestPath = Join-Path $manifestDir ("backup_$timestamp.manifest.json")

$manifestFiles = @()
foreach ($item in $included | Sort-Object Path) {
    $hash = Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
    $manifestFiles += [ordered]@{
        path   = $item.Path
        size   = $item.Size
        sha256 = $hash.Hash.ToLowerInvariant()
    }
}

$manifest = [ordered]@{
    timestamp = $timestamp
    label     = $Label
    archive   = (Join-Path '_backups' ($archiveBaseName + '.zip'))
    files     = $manifestFiles
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Manifest written to: $manifestPath"
