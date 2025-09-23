# Test Suite Health

## Determinism Improvements

* Reworked timeout budget tests (`tests/api/test_timeouts_budget.py`, `tests/api/test_health_timeout.py`, `tests/integrations/test_ch_timeout.py`) to stub `asyncio.wait_for`/HTTP calls instead of depending on wall-clock latency. This removes fragile `sleep` calls and keeps assertions focused on invariants (timeouts wired to configured budgets, correct error payloads).

## Known Watchpoints

* `tests/panel/test_panel_flows.py` and other panel smoke tests exercise multi-step flows. They remain deterministic but can be slower because they traverse the full API stack; keep them in the `test-e2e` target to avoid delaying the basic unit pipeline.
* No randomised tests without seeds were found. Randomised coverage in `tests/intake/test_map_norm_to_raw.py` is seeded (`random.Random(12345)`).

## Execution Profiles

* `make test-unit` skips panel/integration suites and is intended for quick inner-loop runs.
* `make test-e2e` runs panel/integration/e2e suites to validate orchestration paths.
* `make ci-local` mirrors the hosted CI selection of tests and emits `reports/pytest.xml`.

## Follow-ups

* When remote CI telemetry is available, review historical flakes to see whether additional reruns or targeted skips are necessary.
