Param(
  [switch]$Fast,   # быстрый режим: loop-on-fail (pytest -f -q)
  [switch]$All     # полный режим: ptw (pytest-watch) - все тесты при каждом изменении
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  while ($true) {
    if (Test-Path (Join-Path $here "pytest.ini")) { return $here }
    $parent = Split-Path -Parent $here
    if ($parent -eq $here) { throw "pytest.ini not found above $($MyInvocation.MyCommand.Path)" }
    $here = $parent
  }
}

$RepoRoot = Resolve-RepoRoot
Set-Location $RepoRoot

# Активируем venv, если python не виден
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $venv = Join-Path $RepoRoot ".\.venv\Scripts\Activate.ps1"
  if (Test-Path $venv) {
    & $venv
  } else {
    Write-Warning "Virtual env not found, relying on global python."
  }
}

# Базовые env (безопасные дефолты, не затираем если уже выставлены)
if (-not $env:API_KEY) { $env:API_KEY = "local-test-key-123" }
if (-not $env:CONTRACTAI_PROVIDER) { $env:CONTRACTAI_PROVIDER = "mock" }  # prod: 'azure'

Write-Host "[watch] Repo: $RepoRoot"
Write-Host "[watch] API_KEY=$($env:API_KEY)"
Write-Host "[watch] CONTRACTAI_PROVIDER=$($env:CONTRACTAI_PROVIDER)"

# Проверим наличие pytest
python - << 'PYEOF'
import sys
try:
    import pytest  # noqa
except Exception as e:
    print("! pytest is not installed:", e, file=sys.stderr)
    sys.exit(1)
PYEOF
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($All) {
  # Требует pytest-watch
  python - << 'PYEOF'
import sys
try:
    import pytest_watch  # noqa
except Exception as e:
    print("! pytest-watch is not installed:", e, file=sys.stderr)
    sys.exit(1)
PYEOF
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Write-Host "[watch] Starting FULL watch via ptw (pytest-watch)..."
  ptw --runner "pytest -q" --ignore _legacy_disabled --onfail "powershell -command [console]::beep(1000,200)"
  exit $LASTEXITCODE
}

# По умолчанию: быстрый loop-on-fail
Write-Host "[watch] Starting FAST loop-on-fail: pytest -f -q"
python -m pytest -f -q
exit $LASTEXITCODE
