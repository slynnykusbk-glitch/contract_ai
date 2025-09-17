[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = [System.IO.Path]::TrimEndingDirectorySeparator((Resolve-Path -Path (Join-Path $scriptDir '..\..')).Path)

Write-Host "Scanning repository for secret patterns..."

$patterns = @(
    'sk-[A-Za-z0-9_\-]{20,}',
    'AZURE_OPENAI_API_KEY\s*[:=]\s*['"'][A-Za-z0-9_\-]{20,}['"']?',
    'OPENAI_API_KEY\s*[:=]\s*['"'][A-Za-z0-9_\-]{20,}['"']?',
    '-----BEGIN\s+(RSA|EC)\s+PRIVATE KEY-----',
    'connection\s*string.*(password|pwd)\s*='
)

$allFiles = @()
Push-Location -Path $repoRoot
try {
    $tracked = git ls-files 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list tracked files via git."
    }
    $untracked = git ls-files --others --exclude-standard 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list untracked files via git."
    }
    if ($tracked) { $allFiles += $tracked }
    if ($untracked) { $allFiles += $untracked }
} finally {
    Pop-Location
}

$allFiles = $allFiles | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique

$findings = @()
foreach ($relativePath in $allFiles) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        continue
    }
    try {
        $matches = Select-String -Path $fullPath -Pattern $patterns -AllMatches -CaseSensitive:$false
    } catch {
        continue
    }
    if ($matches) {
        foreach ($match in $matches) {
            foreach ($m in $match.Matches) {
                $findings += [pscustomobject]@{
                    Path = $relativePath
                    LineNumber = $match.LineNumber
                    Value = $m.Value
                }
            }
        }
    }
}

if ($findings.Count -gt 0) {
    Write-Host "Potential secret patterns detected:" -ForegroundColor Red
    foreach ($finding in $findings) {
        Write-Host "  $($finding.Path):$($finding.LineNumber): $($finding.Value)"
    }
    exit 2
}

Write-Host "No secret patterns detected."
