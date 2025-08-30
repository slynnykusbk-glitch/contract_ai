param([switch]$Test, [switch]$Demo)

if ($Demo) {
    Write-Host "Running corpus ingest on demo data..."
    python -m contract_review_app.corpus.ingest --dir data/corpus_demo
}
elseif ($Test) {
    pytest -q contract_review_app/tests/corpus --maxfail=1
}
