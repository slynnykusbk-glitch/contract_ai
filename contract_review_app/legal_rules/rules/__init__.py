"""Light‑weight re‑exports for rule helpers.

The actual registry lives in :mod:`contract_review_app.legal_rules.registry`.
This module simply exposes the dictionary of rule handlers under the familiar
``registry`` name so that legacy imports like

``from contract_review_app.legal_rules.rules import registry``

continue to work.
"""

from __future__ import annotations

from ..registry import RULES_REGISTRY as registry, list_rule_names, normalize_clause_type  # noqa: F401

__all__ = ["registry", "list_rule_names", "normalize_clause_type"]

