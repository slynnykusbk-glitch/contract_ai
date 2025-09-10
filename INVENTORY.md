# Inventory

## Decisions
- Python-rules quarantined to core/rules/_legacy_disabled/*, loader only accepts YAML.
- Legacy or orphan tests moved to contract_review_app/tests/_legacy_disabled, CI runs only stable API smoke set; wider coverage will return after cleanup (see task codex/ci-stabilize-orphan-tests).
