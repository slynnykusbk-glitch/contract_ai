"""
Публічний API пакета правил.
Реекспортує модулі з підпакета .rules, щоб тести могли робити:
    from contract_review_app.legal_rules import termination, indemnity, ...
"""

from .rules import (
    base,
    confidentiality,
    definitions,
    force_majeure,
    governing_law,
    indemnity,
    jurisdiction,
    oilgas_master_agreement,
    termination,
)

# Публічний 'registry' — ТІЛЬКИ з кореня пакета (НЕ з .rules)
try:  # noqa: F401
    from . import registry  # type: ignore
except Exception:  # pragma: no cover
    registry = None  # type: ignore

__all__ = [
    "base",
    "confidentiality",
    "definitions",
    "force_majeure",
    "governing_law",
    "indemnity",
    "jurisdiction",
    "oilgas_master_agreement",
    "termination",
    "registry",
]
