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

# Additional citation presets
_UK_GDPR_ART_28 = Citation(
    system="UK",
    instrument="UK GDPR",
    section="Art. 28",
    title="Processor",
    source="ICO",
)

_POCA_2002_S333A = Citation(
    system="UK",
    instrument="POCA 2002",
    section="s.333A",
    title="Proceeds of Crime Act 2002",
    source="UK legislation",
)

_UCTA_1977_S2_1 = Citation(
    system="UK",
    instrument="UCTA 1977",
    section="s.2(1)",
    title="Unfair Contract Terms Act 1977",
    source="UK legislation",
)

_CA_2006_S1159 = Citation(
    system="UK",
    instrument="Companies Act 2006",
    section="s.1159",
    title="Companies Act 2006",
    source="UK legislation",
)

_CA_2006_S1161 = Citation(
    system="UK",
    instrument="Companies Act 2006",
    section="s.1161",
    title="Companies Act 2006",
    source="UK legislation",
)

_DPA_2018_PART2 = Citation(
    system="UK",
    instrument="DPA 2018",
    section="Part 2",
    title="Data Protection Act 2018",
    source="UK legislation",
)

_BRIBERY_ACT_2010_S7 = Citation(
    system="UK",
    instrument="Bribery Act 2010",
    section="s.7",
    title="Bribery Act 2010",
    source="UK legislation",
)

_OIL_GAS_RE = re.compile(r"\boil\b|\bgas\b", re.IGNORECASE)

# lightweight fallback map for keyword search
_KEYWORD_MAP = {
    # general GDPR reference
    "gdpr": _UK_GDPR_ART_28,
    "uk gdpr": _UK_GDPR_ART_28,
    # other instruments
    "poca": _POCA_2002_S333A,
    "tipping": _POCA_2002_S333A,
    "ucta": _UCTA_1977_S2_1,
    "companies act": _CA_2006_S1159,
    "dpa": _DPA_2018_PART2,
    "bribery": _BRIBERY_ACT_2010_S7,
    "oguk": _OGUK_MODEL_AGREEMENT,
    "oil": _OGUK_MODEL_AGREEMENT,
    "gas": _OGUK_MODEL_AGREEMENT,
}

# explicit rule/code mappings (kept for future use; currently empty)
_RULE_MAP: dict[str, Citation] = {}


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

        # UK acts/regs
        if (
            "poca" in message
            or "poca" in code
            or "poca" in rule
            or "tipping" in message
            or "tipping" in code
            or "tipping" in rule
        ):
            citation = deepcopy(_POCA_2002_S333A)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if "ucta" in message or "ucta" in code or "ucta" in rule:
            citation = deepcopy(_UCTA_1977_S2_1)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if (
            "companies act" in message
            or "companies act" in rule
            or "companiesact" in code
            or "companiesact" in rule
            or ("ca" in code and ("1159" in code or "1161" in code))
            or ("ca" in rule and ("1159" in rule or "1161" in rule))
        ):
            if "1161" in message or "1161" in code or "1161" in rule:
                citation = deepcopy(_CA_2006_S1161)
            elif "1159" in message or "1159" in code or "1159" in rule:
                citation = deepcopy(_CA_2006_S1159)
            else:
                citation = deepcopy(_CA_2006_S1159)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if "dpa" in message or "dpa" in code or "dpa" in rule:
            citation = deepcopy(_DPA_2018_PART2)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if (
            "uk gdpr" in message
            or "uk gdpr" in code
            or "uk gdpr" in rule
            or "gdpr" in message
            or "gdpr" in code
            or "gdpr" in rule
        ):
            citation = deepcopy(_UK_GDPR_ART_28)
            logger.info(
                "resolve_citation cid=%s rule=%s",
                f"{citation.instrument} {citation.section}",
                rule,
            )
            return citation

        if "bribery" in message or "bribery" in code or "bribery" in rule:
            citation = deepcopy(_BRIBERY_ACT_2010_S7)
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
