param([string]\ = "help")

switch (\) {
  "lint" { ruff check . ; isort --check-only . ; black --check . ; break }
  "fix"  { ruff check . --fix ; isort . ; black . ; break }
  "test" { \="." ; pytest contract_review_app/tests -q ; break }
  "regen-snapshots" { \="." ; pytest contract_review_app/tests/report/test_renderer_matrix_snapshots.py::test_renderer_snapshots -q -p no:cov --force-regen ; break }
  "test-cov" { \="." ; pytest contract_review_app/tests -q --cov=contract_review_app/report --cov-branch --cov-report=term-missing ; break }
  default { Write-Host "Targets: lint | fix | test | regen-snapshots | test-cov" }
}
