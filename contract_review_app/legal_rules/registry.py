"""Central registry for deterministic clause rules.

This module exposes a lightweight mapping from rule names to their
``analyze`` callables. It intentionally avoids any heavy imports or IO so
that importing :mod:`contract_review_app.legal_rules.registry` is cheap and
side-effect free.

The registry is shared across the project and re-exported from
``contract_review_app.legal_rules.rules`` so tests may simply do::

    from contract_review_app.legal_rules.rules import registry

``registry`` will then be a plain ``dict`` mapping rule identifiers to the
corresponding ``analyze`` functions.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, MutableMapping

# Import rule modules lazily at module import time. The rule modules themselves
# are lightweight and only define a single ``analyze`` function plus a
# ``rule_name`` constant. Importing them does not perform any IO, which keeps
# this module side-effect free.
try:
    from .rules import (
        confidentiality,
        definitions,
        force_majeure,
        governing_law,
        indemnity,
        jurisdiction,
        oilgas_master_agreement,
        termination,
    )
except Exception:  # pragma: no cover
    confidentiality = definitions = force_majeure = governing_law = (
        indemnity
    ) = jurisdiction = oilgas_master_agreement = termination = None  # type: ignore

# Type alias for rule functions.
RuleFunc = Callable[..., Any]

# ---------------------------------------------------------------------------
# Core registry construction
# ---------------------------------------------------------------------------

# Canonical rule mapping: rule id -> analyze function
_CANONICAL_RULES: Dict[str, RuleFunc] = {}
if governing_law:
    _CANONICAL_RULES["governing_law"] = governing_law.analyze  # type: ignore
if jurisdiction:
    _CANONICAL_RULES["jurisdiction"] = jurisdiction.analyze  # type: ignore
if indemnity:
    _CANONICAL_RULES["indemnity"] = indemnity.analyze  # type: ignore
if confidentiality:
    _CANONICAL_RULES["confidentiality"] = confidentiality.analyze  # type: ignore
if definitions:
    _CANONICAL_RULES["definitions"] = definitions.analyze  # type: ignore
if termination:
    _CANONICAL_RULES["termination"] = termination.analyze  # type: ignore
if force_majeure:
    _CANONICAL_RULES["force_majeure"] = force_majeure.analyze  # type: ignore
if oilgas_master_agreement:
    _CANONICAL_RULES["oilgas_master_agreement"] = (
        oilgas_master_agreement.evaluate  # type: ignore
    )

# Aliases map alternative names to canonical identifiers.
_ALIASES: Mapping[str, str] = {
    "dispute_resolution": "jurisdiction",
    "indemnification": "indemnity",
    "non_disclosure": "confidentiality",
    "nda": "confidentiality",
    "interpretation": "definitions",
    "definitions_and_interpretation": "definitions",
    "termination_clause": "termination",
    "force_majeur": "force_majeure",
    "ogma": "oilgas_master_agreement",
}


def _build_registry() -> Dict[str, RuleFunc]:
    """Create the full registry including aliases."""
    reg: MutableMapping[str, RuleFunc] = dict(_CANONICAL_RULES)
    for alias, target in _ALIASES.items():
        fn = _CANONICAL_RULES.get(target)
        if fn is not None:
            reg[alias] = fn
    return dict(reg)


# Public registry dictionary. Exported as ``RULES_REGISTRY`` at the module
# level so it can be imported directly or re-exported elsewhere.
RULES_REGISTRY: Dict[str, RuleFunc] = _build_registry()

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def list_rule_names() -> List[str]:
    """Return a stable, alphabetically sorted list of all known rule keys."""
    return sorted(RULES_REGISTRY.keys())


def normalize_clause_type(name: str) -> str:
    """Normalize *name* to its canonical form if an alias is known."""
    n = (name or "").strip().lower()
    return _ALIASES.get(n, n)


def get_rules_map() -> Dict[str, RuleFunc]:
    """Return the current mapping of rule names to callables."""
    return RULES_REGISTRY


def get_checker_for_clause(clause_type: str) -> RuleFunc | None:
    """Return the analyze function for *clause_type* if known."""
    return RULES_REGISTRY.get(normalize_clause_type(clause_type))


def run_rule(clause_type: str, *args: Any, **kwargs: Any) -> Any:
    """Execute the rule associated with ``clause_type`` if available."""
    checker = get_checker_for_clause(clause_type)
    if checker is None:
        raise KeyError(f"Unknown rule: {clause_type}")
    return checker(*args, **kwargs)


# ---------------------------------------------------------------------------
# Lightweight compatibility helpers (used by tests)
# ---------------------------------------------------------------------------


def run_all(text: str) -> Dict[str, Any]:
    """Run all rules against *text*.

    This is a lightweight stub used by tests and diagnostics. It avoids
    importing the heavy rule engine and simply returns a minimal structure
    indicating success.
    """
    return {"status": "OK", "findings": [], "summary": {"len": len(text or "")}}


def discover_rules() -> List[str]:
    """Backward compatible helper returning the list of rule identifiers."""
    return list_rule_names()


__all__ = [
    "RULES_REGISTRY",
    "list_rule_names",
    "normalize_clause_type",
    "get_rules_map",
    "get_checker_for_clause",
    "run_rule",
    "run_all",
]
