# Acceptance
- panel_selftest.html -> all checks ok
- /health.rules_count > 0
- analyze(sample) returns findings.length >= 1
- /api/qa-recheck does not raise 'Clause.get' error
- If no LLM keys -> draft_text is non-empty stub; meta.model = rulebased
