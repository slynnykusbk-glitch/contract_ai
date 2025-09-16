$repo = Join-Path $env:USERPROFILE 'contract_ai'
$src  = Join-Path $repo 'word_addin_dev\manifest.xml'
$dstD = Join-Path $repo '_shared_catalog'
$dst  = Join-Path $dstD 'manifest.xml'

if (!(Test-Path $dstD)) { New-Item -ItemType Directory -Force -Path $dstD | Out-Null }
Copy-Item -Force $src $dst
Write-Host "Manifest copied to $dst"
