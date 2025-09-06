$ErrorActionPreference="Stop"
pytest -q tests\analysis\test_parser_docx_pdf.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL parser"; exit 1 }
pytest -q tests\analysis\test_classifier_basic.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL classifier"; exit 1 }
pytest -q tests\rules\uk\test_poca_tipping_off.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL poca"; exit 1 }
pytest -q tests\rules\uk\test_ucta_2_1_invalid.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL ucta"; exit 1 }
pytest -q tests\rules\uk\test_outdated_laws.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL outdated"; exit 1 }
pytest -q tests\rules\uk\test_bribery_missing.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL bribery"; exit 1 }
pytest -q tests\rules\test_gl_jurisdiction_conflict.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL gl/jurisdiction"; exit 1 }
pytest -q tests\analysis\test_citation_resolver.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL citations"; exit 1 }
pytest -q tests\panel\test_anchor_sentence_scope.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL anchor"; exit 1 }
pytest -q tests\panel\test_aggregation_dedup.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL dedup"; exit 1 }
pytest -q tests\rules\test_server_threshold.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL threshold"; exit 1 }
pytest -q tests\panel\test_analyze_engine_pipeline.py; if ($LASTEXITCODE -ne 0) { Read-Host "FAIL pipeline"; exit 1 }
Write-Host "OK: Block 2 ALL GREEN"; Read-Host "Press Enter to exit"
