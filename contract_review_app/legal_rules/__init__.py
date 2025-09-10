"""Публічний API пакета правил.

Legacy Python rules have been quarantined to ``core/rules/_legacy_disabled`` and
are no longer importable via this package. Only the loader utilities and the
registry (if available) remain public.
"""

# Публічний 'registry' — ТІЛЬКИ з кореня пакета
try:  # noqa: F401
    from . import registry  # type: ignore
except Exception:  # pragma: no cover
    registry = None  # type: ignore

__all__ = ["registry"]
