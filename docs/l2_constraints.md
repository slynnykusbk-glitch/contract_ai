# L2 constraints quickstart for devs

This note explains how the rule-based L2 constraint layer is wired into the
analysis service, how the expression DSL is structured, and how to inspect the
trace artefacts that capture evaluations.

## Where L2 plugs into the API

* Toggle — the feature is controlled by two environment flags. The L2 code only
  executes when both `FEATURE_LX_ENGINE=1` (enables the LX pipeline) and
  `LX_L2_CONSTRAINTS=1` are present. The second flag is read at import time in
  `contract_review_app/api/app.py`.【F:contract_review_app/api/app.py†L893-L898】
* Execution — in the `/api/analyze` handler the LX snapshot is converted into a
  parameter graph and fed to the constraint engine. The resulting findings are
  merged into the response, and the evaluation artefacts are pushed to the
  shared trace store. Failures are deliberately swallowed to avoid breaking the
  main flow.【F:contract_review_app/api/app.py†L2401-L2416】
* Data shape — `build_param_graph` in
  `contract_review_app/legal_rules/constraints.py` pulls durations, money caps,
  parties, signatures and document flags from the snapshot and segment list. It
  also collects `SourceRef` anchors so the findings can highlight the relevant
  text.【F:contract_review_app/legal_rules/constraints.py†L277-L375】【F:contract_review_app/legal_rules/constraints.py†L375-L456】

When developing a new constraint, you typically extend the parameter graph (if
new data is required) and add a spec entry to `load_constraints()`.

## Constraint DSL cheat sheet

Constraint expressions are parsed once and cached. At runtime they are evaluated
against a `ParamGraph` via a small typed DSL implemented in
`contract_review_app/legal_rules/constraints.py`.

### Identifiers

Identifiers map to strongly-typed getters. Attempting to use an unknown name
raises a syntax error during load. Available identifiers include, among others:

| Identifier | Type | Meaning |
| --- | --- | --- |
| `PaymentTermDays`, `ContractTermDays`, `GraceDays` | duration | Extracted periods in days. |
| `NoticeDays`, `CureDays` | duration | Notice & cure durations. |
| `Cap`, `CapAmount`, `CapCurrency` | money / decimal / string | Liability cap information. |
| `ContractCurrency` | string | Document-level currency. |
| `SurvivalItems` | set<string> | Normalised survival clause topics. |

See `_IDENTIFIER_ACCESSORS` for the full map.【F:contract_review_app/legal_rules/constraints.py†L722-L732】

Missing values propagate as “unknown” (`None`), so comparisons short-circuit and
functions can return `_MISSING`. This allows constraints to skip evaluation when
supporting data is absent.

### Literals and operators

The parser supports string (`"value"`), number (`123` → `Decimal`), set literals
(`{"A", "B"}`) and arithmetic on compatible types (`+` / `-` on durations,
decimals or money). Comparisons support equality/ordering (`==`, `<`, `>=`), and
membership (`∈`, `∉`) against string sets.【F:contract_review_app/legal_rules/constraints.py†L1004-L1087】

### Functions

Functions are evaluated case-insensitively. Core helpers provide null-safe
presence checks and logical composition, while domain-specific functions access
structured contract metadata. Common helpers include:

* `present(value)` / `all_present(a, b, ...)` — truthy checks that handle missing
  arguments.【F:contract_review_app/legal_rules/constraints.py†L1189-L1210】
* `implies(lhs, rhs)` — boolean implication for chaining conditions.【F:contract_review_app/legal_rules/constraints.py†L1210-L1218】
* `same_currency(a, b)` and `non_negative(value)` — validate monetary
  consistency.【F:contract_review_app/legal_rules/constraints.py†L1181-L1189】【F:contract_review_app/legal_rules/constraints.py†L1196-L1203】
* `flag_absent("name")` / `flag_present("name")` — check document flags passed
  from the LX feature extraction stage.【F:contract_review_app/legal_rules/constraints.py†L1234-L1253】
* Domain predicates such as `governing_law_coherent()`,
  `signatures_match_parties()`, `no_mixed_day_kinds()` and
  `survival_baseline_complete()` encapsulate heavier business logic against the
  parameter graph.【F:contract_review_app/legal_rules/constraints.py†L1253-L1296】【F:contract_review_app/legal_rules/constraints.py†L1296-L1313】

New helpers can be added by extending `_call_function` and, if necessary, the
parameter graph builder.

### Constraint catalog

`load_constraints()` enumerates the active rule set. Each entry provides an `id`,
expression string, severity, message template and anchor keys. The evaluation
engine produces `InternalFinding` objects with rule IDs prefixed by `L2::`.
【F:contract_review_app/legal_rules/constraints.py†L1338-L1681】

## Inspecting TRACE artefacts

All constraint runs add an entry to the shared `TRACE` store keyed by the request
CID. The payload contains the serialized parameter graph and the generated L2
findings.【F:contract_review_app/api/app.py†L2407-L2412】【F:contract_review_app/legal_rules/constraints.py†L1698-L1714】

To explore traces locally:

1. Run the API (for example via `uvicorn contract_review_app.main:app` with the
   required feature flags).
2. Hit `/api/analyze` with `X-CID` header set — the CID becomes the trace key.
3. Retrieve recent IDs from `GET /api/trace` and fetch a specific entry as JSON
   (`GET /api/trace/{cid}`) or formatted HTML (`GET /api/trace/{cid}.html`).【F:contract_review_app/api/app.py†L215-L222】【F:contract_review_app/api/app.py†L1783-L1831】

The HTML view renders the JSON under `<pre>` for quick inspection, while the raw
JSON response includes the stored request body, timestamp, parameter graph and L2
findings.

## Local test commands

* `pytest tests/lx/test_l2_ruleset_v1.py` — validates the DSL evaluation logic
  against curated parameter graphs.【F:tests/lx/test_l2_ruleset_v1.py†L51-L247】
* `pytest tests/server/test_analyze_l2_wire.py` — covers the API wiring and trace
  emission when the feature flag is toggled.【F:tests/server/test_analyze_l2_wire.py†L3-L72】

Run both suites before shipping constraint or DSL changes.
