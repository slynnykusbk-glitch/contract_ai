# contract_review_app/legal_rules/rules/__init__.py
"""
Light-weight re-export for the shared rules registry.

This module exposes the dictionary of rule handlers under the familiar
name ``registry`` so legacy imports like:

    from contract_review_app.legal_rules.rules import registry

continue to work.
"""

from __future__ import annotations

# The canonical registry lives in `contract_review_app.legal_rules.registry`.
# Re-export it under the name `registry`.
from ..registry import RULES_REGISTRY as registry, list_rule_names, normalize_clause_type  # noqa: F401

__all__ = ["registry", "list_rule_names", "normalize_clause_type"]
