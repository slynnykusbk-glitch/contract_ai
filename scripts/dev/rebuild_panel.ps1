$ErrorActionPreference = "Stop"

Write-Host "[rebuild_panel] Node/Vite build (word_addin_dev)..."
pushd word_addin_dev
npm ci
npm run build
popd

Write-Host "[rebuild_panel] Sync to static/panel + bump build token..."
python tools/panel_dev_sync.py

Write-Host "[rebuild_panel] Done. Static panel contents:"
Get-ChildItem contract_review_app/contract_review_app/static/panel | Format-Table Name, Length, LastWriteTime -Auto
