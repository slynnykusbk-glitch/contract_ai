$ErrorActionPreference="Stop"
pytest -q tests\panel\test_gpt_draft_payload.py;          if ($LASTEXITCODE -ne 0) { Read-Host "FAIL draft"; exit 1 }
pytest -q tests\panel\test_suggest_ops_minimal.py;        if ($LASTEXITCODE -ne 0) { Read-Host "FAIL suggest"; exit 1 }
pytest -q tests\panel\test_anchor_sentence_scope.py;      if ($LASTEXITCODE -ne 0) { Read-Host "FAIL anchor"; exit 1 }
pytest -q tests\panel\test_analyze_offsets.py;            if ($LASTEXITCODE -ne 0) { Read-Host "FAIL offsets"; exit 1 }
pytest -q tests\security\test_privacy_redaction.py;       if ($LASTEXITCODE -ne 0) { Read-Host "FAIL privacy"; exit 1 }
pytest -q tests\security\test_audit_log.py;               if ($LASTEXITCODE -ne 0) { Read-Host "FAIL audit"; exit 1 }
pytest -q tests\security\test_api_key_auth.py;            if ($LASTEXITCODE -ne 0) { Read-Host "FAIL apikey"; exit 1 }
pytest -q tests\panel\test_panel_flows.py;                if ($LASTEXITCODE -ne 0) { Read-Host "FAIL e2e"; exit 1 }
Write-Host "OK: Block 3 ALL GREEN"; Read-Host "Press Enter to exit"
