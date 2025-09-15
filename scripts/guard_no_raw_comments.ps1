$ErrorActionPreference = "Stop"

# Locate all bundle.js files excluding node_modules
$root = Join-Path $PSScriptRoot ".."
$bundles = Get-ChildItem -Path $root -Recurse -Filter "*bundle.js" -File |
    Where-Object { $_.FullName -notmatch "node_modules" }

foreach ($file in $bundles) {
    if (Select-String -Path $file.FullName -Pattern '/\*' -Quiet) {
        Write-Error "Raw comments detected in bundle $($file.FullName)"
        exit 1
    }
}

Write-Host "No raw comments found in bundles."
