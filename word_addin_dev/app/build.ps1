Param()
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot '..'
& npm --prefix $root run generate:types | Out-Null
$ts = Get-Date -Format 'yyyyMMdd-HHmm'
$dest = Join-Path $PSScriptRoot "build-$ts"
if (-not (Test-Path $dest)) { New-Item -Path $dest -ItemType Directory | Out-Null }

$esbuild = Join-Path $PSScriptRoot '..\..\node_modules\.bin\esbuild.cmd'
if (-not (Test-Path $esbuild)) { $esbuild = 'npx esbuild' }

& $esbuild (Join-Path $PSScriptRoot 'src/panel/index.ts') --bundle --outfile:(Join-Path $dest 'taskpane.bundle.js') --format=iife --platform=browser
Copy-Item (Join-Path $PSScriptRoot 'src/panel/taskpane.html') (Join-Path $dest 'taskpane.html') -Force

Write-Host "Built to $dest"
