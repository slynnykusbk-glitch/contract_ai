from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Optional

from .schemas import Citation, Finding

logger = logging.getLogger(__name__)

# Predefined citations (full objects with snippets)
_UK_GDPR_ART_28_3 = Citation(
    system="UK",
    instrument="UK GDPR",
    section="Art. 28(3)",
    title="Processor contracts",
    source="ICO",
    link=(
        "https://ico.org.uk/for-organisations/guide-to-data-protection/"
        "guide-to-the-uk-gdpr/controllers-and-processors/"
        "contracts-between-controllers-and-processors/"
    ),
    score=1.0,
    evidence_text="Processor must not engage another processor without prior written authorisation.",
)

_OGUK_MODEL_AGREEMENT = Citation(
    system="UK",
    instrument="OGUK Model Agreement",
    section="General reference",
    title="Oil & Gas UK Model Agreement",
    source="OGUK",
    link="https://www.oguk.org.uk/model-form-agreements/",
    score=1.0,
    evidence_text="Standard industry terms for offshore oil and gas contracts.",
)

_OIL_GAS_RE = re.compile(r"\boil\b|\bgas\b", re.IGNORECASE)

_KEYWORD_MAP = {
    "gdpr": _UK_GDPR_ART_28_3,
    "oguk": _OGUK_MODEL_AGREEMENT,
    "oil": _OGUK_MODEL_AGREEMENT,
    "gas": _OGUK_MODEL_AGREEMENT,
}


def resolve_citation(finding: Finding) -> Optional[Citation]:
    """Resolve citations based on rule metadata.

    Args:
        finding: Finding object to inspect.

    Returns:
        A matching :class:`Citation` or ``None`` if no match.
    """

    message = (finding.message or "").lower()
    code = (finding.code or "").lower()
    rule = getattr(finding, "rule", None)

    if "personal data" in message or "conf_gdpr" in code:
        citation = deepcopy(_UK_GDPR_ART_28_3)
        cid = f"{citation.instrument} {citation.section}"
        logger.info("resolve_citation cid=%s rule=%s", cid, rule)
        return citation

    if _OIL_GAS_RE.search(message) or "oguk" in message or "oguk" in code:
        citation = deepcopy(_OGUK_MODEL_AGREEMENT)
        cid = f"{citation.instrument} {citation.section}"
        logger.info("resolve_citation cid=%s rule=%s", cid, rule)
        return citation

    # Fallback keyword-based search (stub)
    for kw, base in _KEYWORD_MAP.items():
        if kw in message or kw in code:
            citation = Citation(
                system=base.system,
                instrument=base.instrument,
                section=base.section,
                title=base.title,
                source=base.source,
                link=base.link,
                score=0.6,
                evidence_text=(finding.evidence or finding.message or "")[:200],
            )
            cid = f"{citation.instrument} {citation.section}"
            logger.info("resolve_citation cid=%s rule=%s", cid, rule)
            return citation

    return None
