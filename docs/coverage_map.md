# Coverage map

The coverage map describes how document segments map to high level obligation zones.
It is stored in [`contract_review_app/legal_rules/coverage_map.yaml`](../contract_review_app/legal_rules/coverage_map.yaml)
and validated through [`coverage_map.py`](../contract_review_app/legal_rules/coverage_map.py).

## Schema overview

```yaml
version: 1
zones:
  - zone_id: payment
    zone_name: "Payment & Invoicing"
    description: "Optional human readable text"
    label_selectors:
      any: ["payment"]      # at least one required
      all: []                # optional set of labels that must all match
      none: []               # optional labels that prevent a match
    entity_selectors:
      amounts: true          # enable entity counters for a zone
      durations: false
      law: false
      jurisdiction: false
    rule_ids_opt: ["pay_late_interest_v1"]  # optional related rules
    weight: 1.0             # reserved for future weighting logic
    required: true          # reserved for validation/UX rules
```

All label selectors are normalised with the same tokeniser used for L0 features.
Aliases such as `governed_by` for `governing_law` are expanded automatically.

## Loader

`coverage_map.load_coverage_map()` reads the YAML file, validates the schema via
Pydantic and returns a cached structure containing:

- the original zone definitions,
- an index of label → zone ids, and
- an index of rule id → zone ids.

The loader is cached with `functools.lru_cache`. Use
`coverage_map.invalidate_cache()` to reload the file in development.

## Coverage computation

`coverage_map.build_coverage()` aggregates L0 labels, entities and rule firing
signals into a compact TRACE block. Inputs:

- `segments`: sequence of segments with labels, entities and spans,
- `dispatch_candidates_by_segment`: list of rule id sets per segment,
- `triggered_rule_ids`: fired YAML rules, and
- `rule_lookup`: optional map of rule metadata (for validation).

The output is a dictionary compatible with `TRACE.add(..., "coverage", ...)`.
Details are clamped to 50 zones and three segments per zone to keep TRACE small.
Raw text snippets are removed during sanitisation.

## Tooling

`tools/coverage_map_lint.py` validates the YAML file and supports a strict mode via
`--strict` or `FEATURE_COVERAGE_LINT_STRICT=1`. The strict mode asserts that the map
contains at least 30 zones.
