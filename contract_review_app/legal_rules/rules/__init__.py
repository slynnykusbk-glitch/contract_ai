"""Rule registry export shim.

Provides a stable ``registry`` object regardless of how the actual
registry is named inside :mod:`contract_review_app.legal_rules.registry`.
"""

# Try to import the root registry module.  This may expose either
# ``RULES_REGISTRY`` or ``registry``.
try:
    from .. import registry as _r  # type: ignore
except Exception:  # pragma: no cover - import errors not fatal
    _r = None  # type: ignore

if _r is not None:
    registry = getattr(_r, "RULES_REGISTRY", getattr(_r, "registry", {}))
else:  # fallback to empty dict when nothing is available
    registry = {}

__all__ = ["registry"]

