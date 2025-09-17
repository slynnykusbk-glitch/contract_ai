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

    if ($normalized.Contains('/')) {
        return '^' + $escaped + '$'
    }

    return '(^|.*/)' + $escaped + '$'
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

$discoveredFiles = Get-ChildItem -Path $repoRoot -File -Recurse
$allFiles = @()

foreach ($file in $discoveredFiles) {
    $relative = $file.FullName.Substring($repoRootWithSep.Length)
    $relative = $relative.TrimStart([char]'\', [char]'/' )
    $relativeNormalized = $relative -replace '\\', '/'
    $shouldExclude = $false
    foreach ($entry in $excludePatterns) {
        if ($entry.Regex.IsMatch($relativeNormalized)) {
            $shouldExclude = $true
            break
        }
    }
    if ($shouldExclude) {
        continue
    }
    $allFiles += [pscustomobject]@{
        Relative = $relativeNormalized
        FullName = $file.FullName
    }
}

$findings = @()
foreach ($file in $allFiles) {
    $relativePath = $file.Relative
    $fullPath = $file.FullName
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
