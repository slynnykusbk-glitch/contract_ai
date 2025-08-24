# STEP1_CLEAN_START.ps1 — build stamp + safe manifest version + versioned SourceLocation + copy to WEF

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log($m){ Write-Host $m -ForegroundColor Green }

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$FRONT_DIR = Join-Path $ROOT "word_addin_dev"
$MANIFEST  = Join-Path $FRONT_DIR "manifest.xml"

# 1) Prepare build
$build = (Get-Date).ToString("yyyyMMdd-HHmm")
$BUILD_DIR = Join-Path $FRONT_DIR ("app\build-{0}" -f $build)
New-Item -ItemType Directory -Force -Path $BUILD_DIR | Out-Null

Copy-Item -Force (Join-Path $FRONT_DIR "taskpane.html")      (Join-Path $BUILD_DIR "taskpane.html")
Copy-Item -Force (Join-Path $FRONT_DIR "taskpane.bundle.js") (Join-Path $BUILD_DIR "taskpane.bundle.js")
if(Test-Path (Join-Path $FRONT_DIR "patch.js")){
  Copy-Item -Force (Join-Path $FRONT_DIR "patch.js") (Join-Path $BUILD_DIR "patch.js")
}

# 2) Bump manifest: safe version and SourceLocation
$officeVersion = "1.0.$((Get-Date).ToString('yyyy')).$((Get-Date).ToString('MMdd'))"
$panelUrl = "https://localhost:3000/app/build-$build/taskpane.html"

$xml = Get-Content $MANIFEST -Raw -Encoding UTF8
$xml = $xml -replace '<Version>.*?</Version>', "<Version>$officeVersion</Version>"
$xml = [regex]::Replace($xml,'SourceLocation\s+DefaultValue="[^"]+"','SourceLocation DefaultValue="'+$panelUrl+'"')
Set-Content $MANIFEST $xml -Encoding UTF8
Log "[OK] Manifest -> Version=$officeVersion, Source=$panelUrl"

# 3) Copy manifest to Shared Folder (WEF\Developer) for manual Insert if needed
$wefDev = Join-Path $env:LOCALAPPDATA "Microsoft\Office\16.0\WEF\Developer"
New-Item -ItemType Directory -Force -Path $wefDev | Out-Null
Copy-Item -Force $MANIFEST (Join-Path $wefDev ("ContractAI-$build.manifest.xml")) | Out-Null
Log "[OK] Copied manifest to $wefDev"
