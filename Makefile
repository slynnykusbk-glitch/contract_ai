.PHONY: lint fix test regen-snapshots test-cov corpus-demo corpus-test rules-lint \
        ci-local test-unit test-e2e

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

ci-local:
	PYTHONPATH=. mkdir -p TRACE trace timings reports
	PYTHONPATH=. pytest -q \
		tests/test_analyze_api.py tests/panel/test_panel_analyze_smoke.py \
		--junitxml=reports/pytest.xml

test-unit:
	PYTHONPATH=. pytest -q tests \
		--ignore=tests/panel \
		--ignore=tests/integration \
		--ignore=tests/integrations \
		--ignore=tests/test_rules_corpus.py

test-e2e:
	PYTHONPATH=. pytest -q \
		tests/panel \
		tests/integration \
		tests/integrations \
		tests/api/test_e2e_smoke.py

corpus-demo:
	@echo "Running corpus ingest on demo data..."
	python -m contract_review_app.corpus.ingest --dir data/corpus_demo

corpus-test:
	pytest -q contract_review_app/tests/corpus --maxfail=1

.PHONY: rules-lint
rules-lint:
	python tools/rules_lint.py

.PHONY: retrieval-build
retrieval-build:
	python -m contract_review_app.retrieval.cli build

.PHONY: retrieval-eval
retrieval-eval:
	python -m contract_review_app.retrieval.eval --golden data/retrieval_golden.yaml --method hybrid --k 5

.PHONY: openapi
openapi:
	python scripts/gen_openapi.py
