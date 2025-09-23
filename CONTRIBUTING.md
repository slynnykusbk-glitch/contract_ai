# Contributing Guide

## Runtime Requirements

* **Python**: 3.11 for the application code. (Corpus tooling is validated against 3.13 in CI, but day-to-day development targets 3.11.)
* **Node.js**: 20.x for building the Office add-in assets.
* **pip**: upgrade to the latest (`python -m pip install -U pip`).

## Environment Bootstrap

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-dev.txt
npm --prefix word_addin_dev ci
```

Set the API key used by tests if running outside GitHub Actions:

```bash
export API_KEY=local-test-key-123
```

Other useful variables (optional):

* `FEATURE_COMPANIES_HOUSE=0` – matches CI defaults.
* `SCHEMA_VERSION` is provided by the app; tests set it automatically.

## Local Commands

* `make ci-local` – reproduces the GitHub CI pytest selection and writes `reports/pytest.xml`.
* `make test-unit` – runs unit tests while skipping panel/integration suites.
* `make test-e2e` – runs panel/integration/e2e flows.
* `make lint` – executes ruff, isort (check mode), and black (check mode).

## Commit Checklist

* Run `python -m pre_commit run -a` once before pushing.
* Ensure `TRACE`, `trace`, `timings`, and `reports` directories exist when invoking tests that emit artifacts (the CI targets do this automatically).
* Capture any new test health notes in `tests/HEALTH.md` and CI observations in `report.md`.
