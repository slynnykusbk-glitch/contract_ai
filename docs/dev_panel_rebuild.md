# Dev panel rebuild & flags

## 1) Запуск backend с фич-флагами
Windows:
  powershell -ExecutionPolicy Bypass -File scripts/dev/run_api_with_flags.ps1
Linux/macOS:
  bash scripts/dev/run_api_with_flags.sh

## 2) Пересборка панели и выкладка в static/panel
Windows:
  powershell -ExecutionPolicy Bypass -File scripts/dev/rebuild_panel.ps1
Linux/macOS:
  bash scripts/dev/rebuild_panel.sh

## 3) Проверка (опционально)
BACKEND_URL=https://127.0.0.1:9443 python tools/quick_smoke.py

## 4) В панели (Word → Taskpane)
Use whole doc → Analyze → в шапке появится «Open TRACE» + бейджи Coverage/Merge.
Anchors в Word берут offsets из TRACE (точнее попадание).
