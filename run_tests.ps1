Get-ChildItem -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
pytest
if ($LASTEXITCODE -eq 0) {
    Write-Host 'tests passed'
} else {
    Write-Host 'tests failed'
    exit $LASTEXITCODE
}
