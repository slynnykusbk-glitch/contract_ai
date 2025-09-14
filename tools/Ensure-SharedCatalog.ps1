# tools/Ensure-SharedCatalog.ps1
$ErrorActionPreference = 'Stop'

# 1) Пути
$RepoRoot   = Resolve-Path (Join-Path $PSScriptRoot '..') | Select-Object -ExpandProperty Path
$CatalogDir = Join-Path $RepoRoot '_shared_catalog'
$ShareName  = '_shared_catalog'                              # имя SMB-шары = имя папки
$SharePath  = "\\$env:COMPUTERNAME\$ShareName"
$ManifestSrc = Join-Path $RepoRoot 'word_addin_dev\manifest.xml'
$ManifestDst = Join-Path $CatalogDir 'ContractAI.xml'

# 2) Папка
if (!(Test-Path $CatalogDir)) { New-Item -ItemType Directory -Path $CatalogDir | Out-Null }

# 3) Шара (idempotent)
try {
  $share = Get-SmbShare -Name $ShareName -ErrorAction Stop
  if ($share.Path -ne $CatalogDir) {
    # если шара указывает не туда — переcоздать
    Remove-SmbShare -Name $ShareName -Force
    New-SmbShare -Name $ShareName -Path $CatalogDir -ReadAccess 'Everyone' -FullAccess $env:USERNAME | Out-Null
  }
} catch {
  New-SmbShare -Name $ShareName -Path $CatalogDir -ReadAccess 'Everyone' -FullAccess $env:USERNAME | Out-Null
}

# 4) Реестр: TrustedCatalogs (HKCU)
$BaseKey = 'HKCU:\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs'
if (!(Test-Path $BaseKey)) { New-Item $BaseKey | Out-Null }

# Сохраняем/читаем постоянный GUID каталога в файле, чтобы он не менялся от запуска к запуску
$GuidFile = Join-Path $CatalogDir '.catalog_guid'
if (Test-Path $GuidFile) {
  $CatGuid = Get-Content $GuidFile -Raw
} else {
  $CatGuid = ([guid]::NewGuid()).Guid
  Set-Content -Path $GuidFile -Value $CatGuid -NoNewline
}
$CatKey = Join-Path $BaseKey $CatGuid
if (!(Test-Path $CatKey)) { New-Item $CatKey | Out-Null }
New-ItemProperty -Path $CatKey -Name Id    -Type String -Value $CatGuid  -Force | Out-Null
New-ItemProperty -Path $CatKey -Name Url   -Type String -Value $SharePath -Force | Out-Null
New-ItemProperty -Path $CatKey -Name Flags -Type DWord  -Value 1         -Force | Out-Null

# 5) Публикация свежего манифеста
if (!(Test-Path $ManifestSrc)) { throw "Manifest not found: $ManifestSrc" }
Copy-Item $ManifestSrc $ManifestDst -Force

Write-Host "Shared catalog ready at: $SharePath"
Write-Host "Registry key: $CatKey"
