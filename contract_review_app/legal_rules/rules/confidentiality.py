from __future__ import annotations
import re
from typing import List, Any, Dict, Optional

from contract_review_app.core.schemas import (
    AnalysisInput,
    AnalysisOutput,
    Finding,
    Citation,
)

rule_name = "confidentiality"  # used by registry discovery

# --- UK citations (strictly UK) ----------------------------------------------
CIT_UK_GDPR = Citation(system="UK", instrument="UK GDPR", section="Arts. 5(1)(f), 32")
CIT_DPA_2018 = Citation(system="UK", instrument="Data Protection Act 2018", section="Part 2")
CIT_SCA_1981 = Citation(system="UK", instrument="Senior Courts Act 1981", section="s.37")
CIT_COCO_1969 = Citation(system="UK", instrument="Coco v A N Clark (Engineers) Ltd [1969] RPC 41", section="breach of confidence")

# --- helpers -----------------------------------------------------------------
_DURATION_RE = re.compile(
    r"\b(for\s+(a\s+period\s+of\s+)?(?P<num>\d{1,2})\s*(year|years|yr|yrs)\b"
    r"|\b(during\s+the\s+term)\s+and\s+for\s+(?P<num2>\d{1,2})\s*(year|years|yr|yrs)\s+after\s+(termination|expiry)\b)",
    re.IGNORECASE,
)

_DEF_RE = re.compile(r"\bconfidential\s+information\b.*?\bmeans\b", re.IGNORECASE | re.DOTALL)

_EXCL_KEYS = [
    r"public\s+domain",
    r"already\s+known|prior\s+knowledge",
    r"independently\s+developed",
    r"lawful\s+possession|rightfully\s+obtained",
    r"required\s+by\s+law|court|regulator|authority|order|disclosure\s+required",
]

_SURVIVE_RE = re.compile(r"\bsurvive[s]?\b.*\b(termination|expiry)\b", re.IGNORECASE | re.DOTALL)
_RETURN_RE = re.compile(r"\b(return|destroy|destruction)\b.*\b(materials|documents|copies|data)\b", re.IGNORECASE | re.DOTALL)
_ONWARD_RE = re.compile(r"\b(disclose|disclosure)\b.*\b(affiliates?|advisers?|advisors?|subcontractors?)\b", re.IGNORECASE)
_LEGAL_DISC_RE = re.compile(r"\b(required|compelled)\s+by\s+(law|court|regulator|authority)\b", re.IGNORECASE)
_INJUNCT_RE = re.compile(r"\b(injunctive\s+relief|interim\s+relief|equitable\s+relief)\b", re.IGNORECASE)

_PD_RE = re.compile(r"\b(personal\s+data|UK\s*GDPR|data\s+protection|DPA\s*2018)\b", re.IGNORECASE)

def _coerce_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return str(obj.get("text", "") or "")
    # pydantic model with .text
    return str(getattr(obj, "text", "") or "")

def _risk_from_findings(findings: List[Finding]) -> str:
    order = {"info": 0, "minor": 1, "major": 2, "critical": 3}
    strongest = 0
    for f in findings:
        lv = getattr(f, "severity_level", None) or "minor"
        strongest = max(strongest, order.get(lv, 1))
    return {0: "low", 1: "medium", 2: "high", 3: "critical"}[strongest]

def _status_from_findings(findings: List[Finding]) -> str:
    levels = [getattr(f, "severity_level", None) or "minor" for f in findings]
    if any(level == "critical" for level in levels):
        return "FAIL"
    if findings:
        return "WARN"
    return "OK"

def _score_from_findings(findings: List[Finding]) -> int:
    penalty = 0
    for f in findings:
        lv = getattr(f, "severity_level", None)
        if lv == "critical":
            penalty += 60
        elif lv == "major":
            penalty += 25
        elif lv == "minor":
            penalty += 10
    return max(0, 100 - penalty)

# --- main rule ---------------------------------------------------------------
def analyze(data: AnalysisInput | Dict[str, Any] | str, **_) -> AnalysisOutput:
    """
    Deterministic rule for confidentiality clauses (UK baseline).
    Accepts AnalysisInput, dict, or plain text; returns AnalysisOutput.
    """
    text = _coerce_text(data).strip()
    findings: List[Finding] = []
    citations = [CIT_COCO_1969]

    if not text:
        findings.append(Finding(
            code="CONF-0",
            message="Clause text is empty or not provided.",
            severity_level="major",
            evidence="Empty text",
            citations=[CIT_COCO_1969],
            tags=["missing", "content"],
        ))

    # 1) Duration present?
    if not _DURATION_RE.search(text):
        findings.append(Finding(
            code="CONF-1",
            message="No confidentiality duration specified.",
            severity_level="major",
            evidence="Missing 'for X years' or 'during the term and for X years after termination'.",
            citations=[CIT_COCO_1969],
            tags=["duration", "temporal-scope"],
        ))

    # 2) Definition present?
    if not _DEF_RE.search(text):
        findings.append(Finding(
            code="CONF-2",
            message="No explicit definition of 'Confidential Information'.",
            severity_level="major",
            evidence="Missing 'Confidential Information means …'.",
            citations=[CIT_COCO_1969],
            tags=["definition"],
        ))

    # 3) Exclusions standard set?
    if not any(re.search(p, text, flags=re.IGNORECASE) for p in _EXCL_KEYS):
        findings.append(Finding(
            code="CONF-3",
            message="Standard exclusions not found (public domain, prior knowledge, independently developed, legally compelled disclosure).",
            severity_level="major",
            evidence="No common exclusions detected.",
            citations=[CIT_COCO_1969],
            tags=["exclusions"],
        ))

    # 4) Survival language?
    if not _SURVIVE_RE.search(text):
        findings.append(Finding(
            code="CONF-4",
            message="No survival language after termination/expiry.",
            severity_level="minor",
            evidence="Missing 'survive termination/expiry'.",
            citations=[CIT_COCO_1969],
            tags=["survival"],
        ))

    # 5) Return/Destroy materials?
    if not _RETURN_RE.search(text):
        findings.append(Finding(
            code="CONF-5",
            message="No obligation to return or destroy confidential materials upon request or termination.",
            severity_level="major",
            evidence="No 'return/destroy' found.",
            citations=[CIT_COCO_1969],
            tags=["return", "destruction"],
        ))

    # 6) Onward disclosure limited (affiliates/advisers)?
    if not _ONWARD_RE.search(text):
        findings.append(Finding(
            code="CONF-6",
            message="No clear control over onward disclosure to affiliates/advisers/subcontractors.",
            severity_level="minor",
            evidence="No onward disclosure restriction found.",
            citations=[CIT_COCO_1969],
            tags=["onward-disclosure"],
        ))

    # 7) Legal disclosure carve-out?
    if not _LEGAL_DISC_RE.search(text):
        findings.append(Finding(
            code="CONF-7",
            message="Legal/regulatory disclosure carve-out not detected.",
            severity_level="minor",
            evidence="No 'required by law/court/regulator' pattern found.",
            citations=[CIT_COCO_1969],
            tags=["carve-out"],
        ))

    # 8) Injunctive/equitable relief?
    if not _INJUNCT_RE.search(text):
        findings.append(Finding(
            code="CONF-8",
            message="No express reference to injunctive/interim/equitable relief.",
            severity_level="minor",
            evidence="No 'injunctive relief' language detected.",
            citations=[CIT_SCA_1981],
            tags=["remedies"],
        ))

    # Data protection hint
    if _PD_RE.search(text):
        findings.append(Finding(
            code="CONF-9",
            message="Personal data referenced: ensure separate data protection terms (UK GDPR / DPA 2018).",
            severity_level="minor",
            evidence="Detected 'personal data' / 'UK GDPR' / 'DPA 2018'.",
            citations=[CIT_UK_GDPR, CIT_DPA_2018],
            tags=["data-protection"],
        ))

    proposed_text = (
        "Confidential Information means any information disclosed by one party to the other, "
        "in any form, that is marked or reasonably understood to be confidential. Confidentiality "
        "obligations apply during the Term and for 5 years after termination. Each party shall: "
        "(a) use the Confidential Information solely for the purpose of performing the Agreement; "
        "(b) not disclose it except to its affiliates and professional advisers who have a strict need to know "
        "and are bound by obligations no less strict; (c) protect it with at least reasonable care; and "
        "(d) on request or upon termination, promptly return or destroy all copies. The obligations do not apply "
        "to information that is in the public domain (other than by breach), already known, independently developed, "
        "or lawfully obtained from a third party, or to disclosures required by law, court or regulator. "
        "Injunctive and other equitable relief may be sought to prevent or stop breaches. "
        "Where personal data is processed, the parties shall comply with the UK GDPR and the Data Protection Act 2018."
    )

    risk = _risk_from_findings(findings)
    status = _status_from_findings(findings)
    score = _score_from_findings(findings)

    return AnalysisOutput(
        clause_type="confidentiality",
        text=text,
        findings=findings,
        proposed_text=proposed_text,
        citations=[*citations],
        score=score,
        risk=risk,
        risk_level=risk,          # legacy compat
        severity=None,            # not needed; left for legacy compat
        status=status,
        category="UK RulePack",
        clause_name="Confidentiality",
        metadata={"rule": rule_name, "version": "1.0"},
    )
