from __future__ import annotations

# Re-export the shared registry so tests can:
#   from contract_review_app.legal_rules.rules import registry
from ..registry import (
    RULES_REGISTRY as registry,
    list_rule_names,
    normalize_clause_type,
)

__all__ = ["registry", "list_rule_names", "normalize_clause_type"]
