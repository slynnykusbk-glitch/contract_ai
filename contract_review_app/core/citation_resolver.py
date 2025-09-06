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

# lightweight fallback map for keyword search
_KEYWORD_MAP = {
    "gdpr": _UK_GDPR_ART_28_3,
    "oguk": _OGUK_MODEL_AGREEMENT,
    "oil": _OGUK_MODEL_AGREEMENT,
    "gas": _OGUK_MODEL_AGREEMENT,
}

# explicit rule/code mappings
_RULE_MAP = {
    "poca": Citation(
        system="UK",
        instrument="POCA 2002",
        section="s.327",
        title="Proceeds of Crime Act 2002",
        source="UK legislation",
    ),
    "ucta": Citation(
        system="UK",
        instrument="UCTA 1977",
        section="s.2",
        title="Unfair Contract Terms Act 1977",
        source="UK legislation",
    ),
    "companiesact": Citation(
        system="UK",
        instrument="Companies Act 2006",
        section="s.172",
        title="Companies Act 2006",
        source="UK legislation",
    ),
    "ukgdpr": Citation(
        system="UK",
        instrument="UK GDPR",
        section="Art. 5",
        title="UK General Data Protection Regulation",
        source="ICO",
    ),
}


def resolve_citation(finding: Finding) -> Optional[Citation]:
    """
    Resolve a single best-matching legal citation for the given finding.

    Notes:
      * All processing is in-memory; contract text is never logged.
      * Returns a fully populated `Citation` or None if no match.
    """
    try:
        message = (finding.message or "").lower()
        code = (getattr(finding, "code", "") or "").lower()
        rule = (getattr(finding, "rule", "") or "").lower()

        for key, cit in _RULE_MAP.items():
            if key in code or key in rule:
                return deepcopy(cit)

        # Strong rules first
        if "personal data" in message or "conf_gdpr" in code:
            citation = deepcopy(_UK_GDPR_ART_28_3)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if _OIL_GAS_RE.search(message) or "oguk" in message or "oguk" in code:
            citation = deepcopy(_OGUK_MODEL_AGREEMENT)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        # Fallback keyword-based stub
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
                    # не логируем текст, но можем вернуть snippet в объекте
                    evidence_text=(
                        getattr(finding, "evidence", None) or finding.message or ""
                    )[:200],
                )
                logger.info(
                    "resolve_citation cid=%s rule=%s",
                    f"{citation.instrument} {citation.section}",
                    rule,
                )
                return citation

        return None
    except Exception as exc:
        logger.warning("resolve_citation failed: %s", exc)
        return None
