from __future__ import annotations

from typing import List, Optional
import re

from .schemas import Citation, Finding

# Predefined citations
_UK_GDPR_ART_28_3 = Citation(system="UK", instrument="UK GDPR", section="Art. 28(3)")
_OGUK_MODEL_AGREEMENT = Citation(
    system="UK", instrument="OGUK Model Agreement", section="General reference"
)

_OIL_GAS_RE = re.compile(r"\boil\b|\bgas\b", re.IGNORECASE)


def resolve_citation(finding: Finding) -> Optional[List[Citation]]:
    """Resolve citations based on rule metadata.

    Args:
        finding: Finding object to inspect.

    Returns:
        List of matching citations or ``None`` if no match.
    """

    message = (finding.message or "").lower()
    code = (finding.code or "").lower()

    if "personal data" in message or "conf_gdpr" in code:
        return [_UK_GDPR_ART_28_3]

    if _OIL_GAS_RE.search(message) or "oguk" in message or "oguk" in code:
        return [_OGUK_MODEL_AGREEMENT]

    return None
