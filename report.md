# CI System Report

## Workflow Inventory

| Workflow | Triggers | Jobs | Runtimes | Key Steps |
| --- | --- | --- | --- | --- |
| `ci.yml` | `push` to `main`, all `pull_request` | `test` | Python 3.11, Node 20 | checkout (fetch-depth 0), setup Python/Node, install dev dependencies, diagnostics (`python -V`, `pip --version`, `pip freeze`, `pre-commit --version`), targeted pre-commit with fallback, prepare `TRACE/trace/timings/reports`, build add-in & panel, pytest with JUnit, artifact uploads (`reports/pytest.xml`, TRACE bundle) |
| `corpus.yml` | `push` to `main`, `pull_request` touching corpus paths | `corpus` | Python 3.13 | checkout (fetch-depth 0), install dev dependencies, diagnostics, prepare artifact directories, pytest corpus suite with JUnit, upload reports, demo corpus ingest, artifact upload |
| `i18n-lint.yml` | all `push`, all `pull_request` | `i18n-lint` | Python 3.11 | checkout (fetch-depth 0), install dev dependencies, diagnostics, run `python tools/i18n_scan.py` (tolerates failures) |
| `manual-backup.yml` | `workflow_dispatch` | `backup` | Ubuntu runner with PowerShell | checkout, secret scan, backup creation, collect manifest paths, upload backup artifact |

## Recent Failure Signals

GitHub Actions history for the last 20 runs is not accessible from this offline environment, so log scraping could not be performed. Flag this as a follow-up action once networked telemetry is available.

## Stabilization Work

* Hardened workflows with full-depth checkouts, consistent dev dependency installation, diagnostics echo, persistent artifact directories, and `if: always()` uploads.
* Ensured pytest emits JUnit XML in all automated suites (`ci.yml`, `corpus.yml`), enabling downstream analysis.
* Reduced time-based flakiness by replacing wall-clock assertions in `tests/api/test_timeouts_budget.py`, `tests/api/test_health_timeout.py`, and `tests/integrations/test_ch_timeout.py` with deterministic instrumentation.

## Outstanding / Deferred

* Need remote access to aggregate historical failures and validate that CI passes on hosted runners.
* No change made to `/api/analyze` per constraints.
