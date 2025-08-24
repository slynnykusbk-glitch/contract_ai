.PHONY: lint fix test regen-snapshots test-cov
lint:
\truff check . && isort --check-only . && black --check .
fix:
\truff check . --fix && isort . && black .
test:
\tPYTHONPATH=. pytest contract_review_app/tests -q
regen-snapshots:
\tPYTHONPATH=. pytest contract_review_app/tests/report/test_renderer_matrix_snapshots.py::test_renderer_snapshots -q -p no:cov --force-regen
test-cov:
\tPYTHONPATH=. pytest contract_review_app/tests -q --cov=contract_review_app/report --cov-branch --cov-report=term-missing
