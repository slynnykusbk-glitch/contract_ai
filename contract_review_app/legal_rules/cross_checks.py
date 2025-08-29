# contract_review_app/legal_rules/cross_checks.py
from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional

from contract_review_app.core.schemas import (
    AnalysisInput,
    AnalysisOutput,
    Finding,
    Citation,
)

# -----------------------------------------------------------------------------
# Helpers: clause lookup and normalization
# -----------------------------------------------------------------------------
def _norm_type(t: str) -> str:
    return (t or "").strip().lower().replace(" ", "_").replace("-", "_")

def _map_by_type(outputs: List[AnalysisOutput]) -> Dict[str, List[int]]:
    m: Dict[str, List[int]] = {}
    for i, o in enumerate(outputs or []):
        ct = _norm_type(getattr(o, "clause_type", None) or getattr(o, "category", "") or "")
        if not ct:
            continue
        m.setdefault(ct, []).append(i)
    return m

def _get_text(o: AnalysisOutput) -> str:
    try:
        return str(getattr(o, "text", "") or "")
    except Exception:
        return ""

def _add_finding(o: AnalysisOutput, code: str, msg: str, severity: str = "major",
                 citations: Optional[List[Citation]] = None) -> None:
    try:
        o.findings = list(o.findings or [])
        o.findings.append(Finding(
            code=str(code),
            message=str(msg),
            severity=severity,
            citations=list(citations or []),
        ))
        # breadcrumbs; executor will re-evaluate metrics
        o.diagnostics = list(o.diagnostics or []) + [f"cross_check: {code}"]
        o.trace = list(o.trace or []) + [f"cross:{code}"]
    except Exception:
        pass

def _first(outputs: List[AnalysisOutput], m: Dict[str, List[int]], keys: List[str]) -> Optional[Tuple[int, AnalysisOutput]]:
    for k in keys:
        ids = m.get(k, [])
        if ids:
            i = ids[0]
            return i, outputs[i]
    return None

def _all(outputs: List[AnalysisOutput], m: Dict[str, List[int]], keys: List[str]) -> List[Tuple[int, AnalysisOutput]]:
    out: List[Tuple[int, AnalysisOutput]] = []
    for k in keys:
        for i in m.get(k, []):
            out.append((i, outputs[i]))
    return out

# -----------------------------------------------------------------------------
# Capacity detector (kept from previous version; UK-focused but generic)
# -----------------------------------------------------------------------------
_CAPACITY_PATTERNS = [
    r"\bincorporated\s+(?:in|under\s+the\s+laws\s+of)\b",
    r"\bplace\s+of\s+incorporation\b",
    r"\bincorporated\s+and\s+registered\s+in\s+(?:england|scotland|wales|northern\s+ireland|england\s+and\s+wales)\b",
    r"\b(registered|registration)\s+number\b",
    r"\b(company)\s+(?:number|no\.)\b",
    r"\bregistration\s+no\.\b",
    r"\bcompanies\s+house\s+(?:number|no\.)\b",
    r"\bregistered\s+office\b",
    r"\bprincipal\s+place\s+of\s+business\b",
    r"\bregistered\s+in\s+(?:england|scotland|wales|northern\s+ireland|england\s+and\s+wales)\b",
]
_CAPACITY_RX = re.compile("|".join(_CAPACITY_PATTERNS), re.IGNORECASE)

def _has_party_capacity(text: str) -> bool:
    return bool(_CAPACITY_RX.search(text or ""))

# -----------------------------------------------------------------------------
# Parsers for GL / Jurisdiction (heuristic, deterministic, fast)
# -----------------------------------------------------------------------------
_UK_LAW_RX = re.compile(
    r"\blaws?\s+of\s+(england\s+and\s+wales|england|scotland|northern\s+ireland)\b", re.IGNORECASE
)
_JUR_RX = re.compile(
    r"\b(?:courts?\s+of|exclusive\s+jurisdiction\s+of)\s+(england\s+and\s+wales|england|scotland|northern\s+ireland)\b",
    re.IGNORECASE,
)
_GENERIC_JUR_RX = re.compile(r"\bexclusive\s+jurisdiction\b", re.IGNORECASE)

def _parse_gl(text: str) -> Optional[str]:
    m = _UK_LAW_RX.search(text or "")
    if m:
        val = m.group(1).lower().replace(" ", "_")
        return val  # "england_and_wales", "england", "scotland", "northern_ireland"
    return None

def _parse_jur(text: str) -> Optional[str]:
    m = _JUR_RX.search(text or "")
    if m:
        return m.group(1).lower().replace(" ", "_")
    # If generic "exclusive jurisdiction" appears without region, tag as unknown
    if _GENERIC_JUR_RX.search(text or ""):
        return "unknown_exclusive"
    return None

# -----------------------------------------------------------------------------
# TERM helpers: notice/cure detection; survival list extraction
# -----------------------------------------------------------------------------
_NOTICE_RX = re.compile(r"\b(?:\d{1,3})\s*(?:calendar\s+)?days?\b.*\bnotice\b", re.IGNORECASE | re.DOTALL)
_CURE_RX = re.compile(r"\b(cure|remedy)\s+period\b", re.IGNORECASE)
_FOR_CONVENIENCE_RX = re.compile(r"\btermination\s+for\s+convenience\b|\bfor\s+convenience\b", re.IGNORECASE)
_SURVIVE_RX = re.compile(
    r"\bthe\s+following\s+provisions\s+shall\s+survive\b|\bshall\s+survive\s+termination\b",
    re.IGNORECASE,
)
_SURVIVAL_ITEM_RX = re.compile(
    r"\b(" 
    r"confidentiality|"
    r"limitation\s+of\s+liability|"
    r"liability\s+cap|"
    r"indemnity|"
    r"intellectual\s+property|"
    r"governing\s+law|"
    r"jurisdiction"
    r")\b",
    re.IGNORECASE,
)

def _has_notice(text: str) -> bool:
    return bool(_NOTICE_RX.search(text or ""))

def _has_cure(text: str) -> bool:
    return bool(_CURE_RX.search(text or ""))

def _has_for_convenience(text: str) -> bool:
    return bool(_FOR_CONVENIENCE_RX.search(text or ""))

def _extract_survival_items(text: str) -> List[str]:
    out: List[str] = []
    if not _SURVIVE_RX.search(text or ""):
        return out
    for m in _SURVIVAL_ITEM_RX.finditer(text or ""):
        out.append(m.group(1).lower())
    return sorted(set(out))

# -----------------------------------------------------------------------------
# CONF vs DP helpers
# -----------------------------------------------------------------------------
_DP_HINT_RX = re.compile(r"\b(uk\s*gdpr|gdpr|data\s+protection\s+act|controller|processor|processing)\b", re.IGNORECASE)
_CONF_DP_RX = re.compile(r"\b(confidential|confidentiality)\b", re.IGNORECASE)

def _has_dp_signals(text: str) -> bool:
    return bool(_DP_HINT_RX.search(text or ""))

def _conf_mentions_dp(text: str) -> bool:
    return bool(_DP_HINT_RX.search(text or ""))

# -----------------------------------------------------------------------------
# FM vs Payment helpers
# -----------------------------------------------------------------------------
_FM_RX = re.compile(r"\bforce\s+majeure\b", re.IGNORECASE)
_FM_EXCLUDES_PAY_RX = re.compile(r"\b(?:shall\s+not\s+apply\s+to|does\s+not\s+excuse)\s+payment\b", re.IGNORECASE)
_PAYMENT_RX = re.compile(r"\b(payment|fees|charges|consideration)\b", re.IGNORECASE)

# -----------------------------------------------------------------------------
# IP vs License helpers
# -----------------------------------------------------------------------------
_IP_OWNER_RX = re.compile(r"\b(all|any)\s+intellectual\s+property\s+(rights?\s+)?(?:remain\s+with|are\s+owned\s+by)\b", re.IGNORECASE)
_LICENSE_BROAD_RX = re.compile(r"\b(perpetual|irrevocable|worldwide|transferable|sublicensable)\b", re.IGNORECASE)

# -----------------------------------------------------------------------------
# Cross-checks implementation
# -----------------------------------------------------------------------------
def cross_check_clauses(
    inputs: List[AnalysisInput],
    outputs: List[AnalysisOutput],
) -> List[AnalysisOutput]:
    """
    Post-process rule outputs with cross-document signals.
    Adjusts/augments findings; never raises; minimal, deterministic work only.
    Status/score are recomputed by executor after this pass.
    """

    # Build full_text (for capacity / DP hints)
    full_text = ""
    for inp in inputs or []:
        try:
            md = inp.metadata or {}
            if isinstance(md, dict) and isinstance(md.get("full_text"), str) and md["full_text"]:
                full_text = md["full_text"]
                break
        except Exception:
            pass
    if not full_text:
        parts = []
        for inp in inputs or []:
            try:
                if isinstance(inp.text, str) and inp.text:
                    parts.append(inp.text)
            except Exception:
                continue
        full_text = "\n\n".join(parts)

    # Map clauses by normalized type
    by_type = _map_by_type(outputs)

    # ---------- 1) GL <-> JUR alignment -------------------------------------
    gl_ref = _first(outputs, by_type, ["governing_law", "governinglaw", "law", "applicable_law"])
    jur_ref = _first(outputs, by_type, ["jurisdiction", "venue", "forum"])

    if gl_ref:
        i_gl, o_gl = gl_ref
        gl_text = _get_text(o_gl)
        gl_loc = _parse_gl(gl_text)
        if jur_ref:
            i_jur, o_jur = jur_ref
            jur_text = _get_text(o_jur)
            jur_loc = _parse_jur(jur_text)

            mismatch = False
            if gl_loc and jur_loc and jur_loc != "unknown_exclusive" and gl_loc != jur_loc:
                mismatch = True
            if gl_loc and (jur_loc is None or jur_loc == "unknown_exclusive"):
                mismatch = True

            if mismatch:
                _add_finding(o_gl, "GL_103",
                             "Governing law and forum selection appear misaligned; consider aligning law and courts.",
                             severity="major",
                             citations=[Citation(system="UK", instrument="General contract practice", section="GL↔JUR", title="General contract practice", source_type="practice", source_id="gl_jur")])
                _add_finding(o_jur, "JUR_102",
                             "Jurisdiction clause may conflict with chosen governing law; clarify forum or adjust law.",
                             severity="major",
                             citations=[Citation(system="UK", instrument="General contract practice", section="GL↔JUR", title="General contract practice", source_type="practice", source_id="gl_jur")])

    # ---------- 2) TERM <-> NOTICE / LoL -------------------------------------
    term_refs = _all(outputs, by_type, ["termination", "term_and_termination", "termination_clause"])

    for _, o_term in term_refs:
        t = _get_text(o_term)
        if _has_for_convenience(t) and not _has_notice(t):
            _add_finding(
                o_term, "TERM_205",
                "Termination for convenience without explicit notice period; add clear notice (e.g., 30 days).",
                severity="major",
            )
        # cure period hint
        if re.search(r"\bfor\s+cause\b", t, re.IGNORECASE) and not _has_cure(t):
            _add_finding(
                o_term, "TERM_212",
                "Termination for cause without a cure period; consider adding a reasonable cure window.",
                severity="minor",
            )

    # ---------- 3) Survival list ---------------------------------------------
    # Try to find explicit survival list either in termination or a dedicated survival clause
    survival_sources = term_refs + _all(outputs, by_type, ["survival", "survival_of_terms"])
    survival_seen: List[str] = []
    for _, o_src in survival_sources:
        items = _extract_survival_items(_get_text(o_src))
        survival_seen.extend(items)
    survival_seen = sorted(set(survival_seen))

    if survival_sources:
        # check missing critical survivors
        missing: List[str] = []
        for k in ["confidentiality", "limitation of liability", "indemnity"]:
            if not any(k in x for x in survival_seen):
                missing.append(k)
        if missing:
            # add finding to the first termination/survival clause
            _, o_first = survival_sources[0]
            _add_finding(
                o_first, "TERM_260",
                "Survival list may be incomplete; consider adding: " + ", ".join(missing) + ".",
                severity="major",
            )

    # ---------- 4) CONF <-> DP -----------------------------------------------
    conf_ref = _first(outputs, by_type, ["confidentiality", "nda", "non_disclosure"])
    if conf_ref:
        i_conf, o_conf = conf_ref
        conf_text = _get_text(o_conf)
        if _has_dp_signals(full_text) and not _conf_mentions_dp(conf_text):
            _add_finding(
                o_conf, "CONF_114",
                "Confidentiality clause lacks data protection carve-outs/references (UK GDPR/DPA).",
                severity="major",
                citations=[Citation(system="UK", instrument="UK GDPR / DPA 2018", section="General reference", title="UK GDPR / DPA 2018", source_type="law", source_id="uk_gdpr_dpa_2018")],
            )

    # ---------- 5) FM <-> Payment --------------------------------------------
    fm_ref = _first(outputs, by_type, ["force_majeure", "force-majeure", "fm"])
    if fm_ref:
        i_fm, o_fm = fm_ref
        fm_text = _get_text(o_fm)
        if _FM_RX.search(fm_text):
            mentions_payment = bool(_PAYMENT_RX.search(fm_text))
            excludes_payment = bool(_FM_EXCLUDES_PAY_RX.search(fm_text))
            # If FM exists and payment is not explicitly excluded, suggest clarifying carve-out
            if not excludes_payment and mentions_payment:
                _add_finding(
                    o_fm, "FM_207",
                    "Force majeure should not excuse payment obligations; add an explicit carve-out.",
                    severity="major",
                )

    # ---------- 6) IP ownership <-> License scope ----------------------------
    ip_refs = _all(outputs, by_type, ["intellectual_property", "ip", "ip_rights"])
    lic_refs = _all(outputs, by_type, ["license", "licence", "licensing"])
    if ip_refs and lic_refs:
        # Use first IP and first License for a simple coherence check
        _, o_ip = ip_refs[0]
        _, o_lic = lic_refs[0]
        ip_text = _get_text(o_ip)
        lic_text = _get_text(o_lic)

        owner_strict = bool(_IP_OWNER_RX.search(ip_text))
        license_broad = bool(_LICENSE_BROAD_RX.search(lic_text))
        if owner_strict and license_broad:
            _add_finding(
                o_lic, "IP_402",
                "License scope may be inconsistent with strict IP ownership; narrow scope or add limitations.",
                severity="major",
            )

    # ---------- 7) Definitions capacity downgrade (legacy rule) --------------
    if _has_party_capacity(full_text):
        for idx in by_type.get("definitions", []):
            o = outputs[idx]
            changed = False
            for f in list(getattr(o, "findings", []) or []):
                if (getattr(f, "code", "") or "").upper() == "DEF_009":
                    if getattr(f, "severity", "").lower() != "info":
                        f.severity = "info"
                        base_msg = getattr(f, "message", "No hint of parties’ legal capacity.")
                        if "Cross-check" not in (base_msg or ""):
                            f.message = base_msg + " (Cross-check: capacity found elsewhere in the document.)"
                        changed = True
            if changed:
                o.diagnostics = list(o.diagnostics or []) + [
                    "Cross-check: party capacity detected; DEF_009 downgraded to info."
                ]
                o.trace = list(o.trace or []) + ["cross_check: capacity=True -> DEF_009 -> info"]

    return outputs
