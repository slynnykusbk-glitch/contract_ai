.PHONY: lint fix test regen-snapshots test-cov corpus-demo corpus-test

lint:
	ruff check . && isort --check-only . && black --check .

fix:
	ruff check . --fix && isort . && black .

test:
	PYTHONPATH=. pytest contract_review_app/tests -q

regen-snapshots:
	PYTHONPATH=. pytest contract_review_app/tests/report/test_renderer_matrix_snapshots.py::test_renderer_snapshots -q -p no:cov --force-regen

test-cov:
	PYTHONPATH=. pytest contract_review_app/tests -q --cov=contract_review_app/report --cov-branch --cov-report=term-missing

corpus-demo:
	@echo "Running corpus ingest on demo data..."
	python -m contract_review_app.corpus.ingest --dir data/corpus_demo

corpus-test:
\tpytest -q contract_review_app/tests/corpus --maxfail=1

.PHONY: retrieval-build
retrieval-build:
\tpython -m contract_review_app.retrieval.cli build

.PHONY: retrieval-eval
retrieval-eval:
	python -m contract_review_app.retrieval.eval --golden data/retrieval_golden.yaml --method hybrid --k 5
