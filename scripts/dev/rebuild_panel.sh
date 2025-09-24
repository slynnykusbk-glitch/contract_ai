#!/usr/bin/env bash
set -euo pipefail

echo "[rebuild_panel] Node/Vite build (word_addin_dev)..."
pushd word_addin_dev >/dev/null
npm ci
npm run build
popd >/dev/null

echo "[rebuild_panel] Sync to static/panel + bump build token..."
python tools/panel_dev_sync.py

echo "[rebuild_panel] Done. Static panel contents:"
ls -lah contract_review_app/contract_review_app/static/panel
