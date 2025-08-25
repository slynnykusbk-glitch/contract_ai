from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import re

# Public API:
# evaluate(text, sections) -> (analyses: list[dict], metrics: dict)

# ----------------------- helpers -----------------------
_RISK_ORD = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_ORD_RISK = ["low", "medium", "high", "critical"]

def _risk_to_ord(s: str) -> int:
    return _RISK_ORD.get((s or "medium").lower(), 1)

def _ord_to_risk(i: int) -> str:
    if i < 0: i = 0
    if i >= len(_ORD_RISK): i = len(_ORD_RISK) - 1
    return _ORD_RISK[i]

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def _span_dict(start: int, length: int) -> Dict[str, int]:
    return {"start": max(0, int(start)), "length": max(0, int(length))}

def _find_first(pats: List[re.Pattern], text: str) -> Optional[re.Match]:
    for p in pats:
        m = p.search(text)
        if m:
            return m
    return None

def _compile(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]

def _sec_for_clause(sections: List[Dict[str, Any]], prefer: List[str], title_keywords: List[str]) -> Tuple[str, Dict[str, int]]:
    # choose first section where clause_type matches prefer, else title has keyword
    for c in prefer:
        for s in sections:
            if str(s.get("clause_type", "")).lower() == c.lower():
                sp = s.get("span") or {}
                return (str(s.get("title") or c), _span_dict(int(sp.get("start", 0)), int(sp.get("length", 0))))
    # title keyword fallback
    for s in sections:
        title = str(s.get("title") or "")
        for kw in title_keywords:
            if re.search(kw, title, re.IGNORECASE):
                sp = s.get("span") or {}
                return (title, _span_dict(int(sp.get("start", 0)), int(sp.get("length", 0))))
    # none: document as a whole
    return ("", _span_dict(0, 0))

def _ctx(text: str, span: Dict[str, int], radius: int = 1200) -> str:
    n = len(text or "")
    a = max(0, span["start"] - radius)
    b = min(n, span["start"] + span["length"] + radius)
    return (text or "")[a:b]

def _mk_finding(code: str, message: str, severity: str, match_span: Optional[Tuple[int, int]], section_span: Dict[str, int]) -> Dict[str, Any]:
    if match_span is None:
        span = section_span
    else:
        s, e = match_span
        span = _span_dict(s, max(0, e - s))
    sev_map = {"low": "minor", "medium": "major", "high": "critical"}
    sev = sev_map.get(str(severity).lower(), str(severity))
    return {"code": code, "message": message, "severity": sev, "span": span}

def _mk_analysis(clause_type: str, title: str, span: Dict[str, int], status: str, risk_level: str, score: int, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "clause_type": clause_type,
        "title": title,
        "span": span,
        "status": status,
        "risk_level": risk_level,
        "score": _clamp(int(score), -100, 100),
        "findings": findings,
    }

# ----------------------- core checks -----------------------
def _check_limitation_of_liability(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "limitation_of_liability"
    title, span = _sec_for_clause(
        sections,
        ["liability", "limitation_of_liability", "limitation", "limitation liability"],
        [r"\blimitation of liability\b", r"\bliability\b", r"\bcap\b"]
    )
    ctx = _ctx(text, span)

    pats_cap = _compile([r"\bcap(?:ped)?\b", r"\blimit(?:ation)?\b", r"\bmaximum\b", r"\baggregate\b"])
    pats_amount = _compile([r"£\s?\d", r"\bGBP\b", r"\b\d{1,3}\s?%"])
    pats_carveouts = _compile([
        r"\bconfidentialit(y|ies)\b",
        r"\bintellectual property\b|\bIP\b|\binfringement\b",
        r"\bbriber(y|y act)\b|\banti[- ]?corruption\b",
        r"\bdeath\b|\bpersonal injury\b",
        r"\bdata protection\b|\bGDPR\b|\bUK GDPR\b",
        r"\bfraud\b",
        r"\bwilful misconduct\b|\bgross negligence\b",
    ])

    findings: List[Dict[str, Any]] = []
    status = "OK"
    risk = "medium"
    score = 10

    m_cap_kw = _find_first(pats_cap, ctx)
    m_amt = _find_first(pats_amount, ctx)
    carve_hits = []
    for p in pats_carveouts:
        mm = p.search(ctx)
        if mm:
            carve_hits.append(mm)

    if not m_cap_kw or not m_amt:
        status = "WARN"
        risk = "high"
        score = -30
        findings.append(_mk_finding("LLI-CAP-MISSING", "No explicit liability cap amount detected", "high", None, span))

    if len(carve_hits) == 0:
        status = "FAIL"
        risk = "critical"
        score = -60
        findings.append(_mk_finding("LLI-CARVEOUTS-MISSING", "No standard carve-outs detected (confidentiality, IP, bribery, personal injury, data protection, fraud).", "critical", None, span))

    return _mk_analysis(clause_type, title or "Limitation of Liability", span, status, risk, score, findings)

def _check_anti_bribery(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "anti_bribery"
    title, span = _sec_for_clause(
        sections,
        ["anti_bribery", "compliance", "ethics"],
        [r"\banti[- ]?briber(y|y)\b", r"\banti[- ]?corruption\b", r"\bbribery act\b"]
    )
    ctx = _ctx(text, span)
    has_ba2010 = re.search(r"\bBribery Act\s*2010\b", ctx, re.IGNORECASE) is not None

    findings: List[Dict[str, Any]] = []
    if has_ba2010:
        status, risk, score = "OK", "low", 10
    else:
        status, risk, score = "WARN", "medium", -10
        findings.append(_mk_finding("AB-UKREF-MISSING", "UK reference not detected (e.g., Bribery Act 2010).", "medium", None, span))

    return _mk_analysis(clause_type, title or "Anti-Bribery", span, status, risk, score, findings)

def _check_exhibit_L_present(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "exhibits_L_present"
    span = _span_dict(0, 0)
    has_exh_l = re.search(r"\bExhibit\s*L\b", text or "", re.IGNORECASE) is not None
    findings: List[Dict[str, Any]] = []
    if has_exh_l:
        status, risk, score = "OK", "low", 5
    else:
        status, risk, score = "FAIL", "high", -40
        findings.append(
            _mk_finding(
                "EXHIBIT-L-MISSING",
                "Exhibit L (Information Systems Access and Data Security) not referenced.",
                "high",
                None,
                span,
            )
        )
    return _mk_analysis(clause_type, "Exhibit L", span, status, risk, score, findings)

def _check_exhibit_M_present(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "exhibits_M_present"
    span = _span_dict(0, 0)
    has_exh_m = re.search(r"\bExhibit\s*M\b", text or "", re.IGNORECASE) is not None
    findings: List[Dict[str, Any]] = []
    if has_exh_m:
        status, risk, score = "OK", "low", 5
    else:
        status, risk, score = "FAIL", "high", -40
        findings.append(
            _mk_finding(
                "EXHIBIT-M-MISSING",
                "Exhibit M (Data Protection) not referenced.",
                "high",
                None,
                span,
            )
        )
    return _mk_analysis(clause_type, "Exhibit M", span, status, risk, score, findings)

def _check_information_security(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "information_security"
    title, span = _sec_for_clause(
        sections,
        ["information_security", "confidentiality", "information_systems"],
        [r"information systems? access", r"data security", r"company systems"],
    )
    ctx = _ctx(text, span)
    has_access = re.search(r"information systems? access|company systems|data security", ctx, re.IGNORECASE) is not None
    has_exh_l = re.search(r"\bExhibit\s*L\b", ctx, re.IGNORECASE) is not None
    findings: List[Dict[str, Any]] = []
    if has_access and has_exh_l:
        status, risk, score = "OK", "low", 8
    elif has_access and not has_exh_l:
        status, risk, score = "FAIL", "high", -40
        findings.append(
            _mk_finding(
                "IS-EXHIBIT-L-MISSING",
                "Information Systems access detected but Exhibit L reference missing.",
                "high",
                None,
                span,
            )
        )
    else:
        status, risk, score = "OK", "low", 5
    return _mk_analysis(clause_type, title or "Information Security", span, status, risk, score, findings)

def _check_data_protection(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "data_protection"
    title, span = _sec_for_clause(
        sections,
        ["data_protection", "privacy", "gdpr"],
        [r"\bdata protection\b", r"\bGDPR\b", r"\bUK GDPR\b", r"\bExhibit\s*M\b"]
    )
    ctx = _ctx(text, span)
    has_pd = re.search(r"personal data|GDPR|Data Protection Act\s*2018", ctx, re.IGNORECASE) is not None
    has_exh_m = re.search(r"\bExhibit\s*M\b", ctx, re.IGNORECASE) is not None
    ok = has_pd and has_exh_m
    findings: List[Dict[str, Any]] = []
    if ok:
        status, risk, score = "OK", "low", 10
    elif has_pd and not has_exh_m:
        status, risk, score = "FAIL", "high", -40
        findings.append(
            _mk_finding(
                "DP-EXHIBIT-MISSING",
                "Personal data detected but Exhibit M reference missing. Insert reference to Exhibit M – Data Protection.",
                "high",
                None,
                span,
            )
        )
    else:
        status, risk, score = "WARN", "medium", -15
        findings.append(
            _mk_finding(
                "DP-REF-MISSING",
                "No explicit GDPR/UK GDPR or Data Protection reference detected.",
                "medium",
                None,
                span,
            )
        )
    return _mk_analysis(clause_type, title or "Data Protection", span, status, risk, score, findings)

def _check_export_control(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "export_control"
    title, span = _sec_for_clause(
        sections,
        ["export_control", "sanctions", "compliance"],
        [r"\bexport control\b", r"\btrade sanctions?\b", r"\bimporter of record\b", r"\bexporter of record\b"]
    )
    ctx = _ctx(text, span)
    has_export = re.search(r"\bexport control\b|\btrade sanctions?\b", ctx, re.IGNORECASE) is not None
    has_ior = re.search(r"\bimporter of record\b", ctx, re.IGNORECASE) is not None
    has_eor = re.search(r"\bexporter of record\b", ctx, re.IGNORECASE) is not None

    findings: List[Dict[str, Any]] = []
    if has_export and has_ior and has_eor:
        status, risk, score = "OK", "low", 10
    else:
        status, risk, score = "WARN", "medium", -10
        if not has_export:
            findings.append(_mk_finding("EC-OBLIGATIONS-MISSING", "No explicit export control/sanctions compliance obligation detected.", "medium", None, span))
        if not has_ior:
            findings.append(_mk_finding("EC-IOR-MISSING", "Importer of Record not defined.", "medium", None, span))
        if not has_eor:
            findings.append(_mk_finding("EC-EOR-MISSING", "Exporter of Record not defined.", "medium", None, span))
    return _mk_analysis(clause_type, title or "Export Control", span, status, risk, score, findings)

def _check_insurance(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "insurance"
    title, span = _sec_for_clause(
        sections,
        ["insurance"],
        [r"\binsurance\b"]
    )
    ctx = _ctx(text, span)
    has_types = any([
        re.search(r"\bemployers[’']?\s*liabilit(y|ies)\b|\bEL\b", ctx, re.IGNORECASE),
        re.search(r"\b(public|general)\s+liabilit(y|ies)\b|\bPL\b|\bGL\b", ctx, re.IGNORECASE),
        re.search(r"\bprofessional\s+indemnity\b|\bPI\b", ctx, re.IGNORECASE),
    ])
    has_limits = re.search(r"(£|\bGBP\b|\bUSD\b)\s?\d", ctx, re.IGNORECASE) is not None or \
                 re.search(r"\bper (?:occurrence|claim)\b|\baggregate\b", ctx, re.IGNORECASE) is not None

    findings: List[Dict[str, Any]] = []
    if has_types and has_limits:
        status, risk, score = "OK", "low", 8
    elif has_types and not has_limits:
        status, risk, score = "WARN", "medium", -10
        findings.append(_mk_finding("INS-LIMITS-MISSING", "Insurance limits not detected.", "medium", None, span))
    else:
        status, risk, score = "WARN", "high", -20
        findings.append(_mk_finding("INS-TYPES-MISSING", "Required insurance types (EL/PL/GL/PI) not detected.", "high", None, span))
    return _mk_analysis(clause_type, title or "Insurance", span, status, risk, score, findings)

def _check_hse(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "hse"
    title, span = _sec_for_clause(
        sections,
        ["hse", "hsse", "safety", "health_and_safety"],
        [r"\bHSE\b|\bHSSE\b", r"\bLife Saving Rules\b", r"\boffshore\b", r"\bExhibit\s*(A|E|F)\b"]
    )
    ctx = _ctx(text, span)
    ok = any([
        re.search(r"\bLife Saving Rules\b", ctx, re.IGNORECASE),
        re.search(r"\bHSE\b|\bHSSE\b", ctx, re.IGNORECASE),
        re.search(r"\boffshore\b", ctx, re.IGNORECASE),
        re.search(r"\bExhibit\s*(A|E|F)\b", ctx, re.IGNORECASE),
    ])
    findings: List[Dict[str, Any]] = []
    if ok:
        status, risk, score = "OK", "low", 8
    else:
        status, risk, score = "WARN", "medium", -10
        findings.append(_mk_finding("HSE-REFS-MISSING", "No HSE/HSSE references (e.g., Life Saving Rules, offshore exhibits) detected.", "medium", None, span))
    return _mk_analysis(clause_type, title or "HSE / HSSE", span, status, risk, score, findings)

def _check_termination(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "termination"
    title, span = _sec_for_clause(
        sections,
        ["termination", "term_and_termination", "term"],
        [r"\btermination\b", r"\bterm(?: and)? termination\b"]
    )
    ctx = _ctx(text, span)
    company_toc = re.search(r"\bterminate(?:s|d|) for convenience\b|\btermination for convenience\b|\bCompany may terminate\b", ctx, re.IGNORECASE) is not None
    contractor_rights = re.search(r"\bContractor may terminate\b|\bterminate (?:for )?non[- ]payment\b|\bmaterial breach by Company\b", ctx, re.IGNORECASE) is not None

    findings: List[Dict[str, Any]] = []
    if company_toc and contractor_rights:
        status, risk, score = "OK", "low", 8
    elif company_toc and not contractor_rights:
        status, risk, score = "WARN", "medium", -12
        findings.append(_mk_finding("TERM-CONTRACTOR-RIGHTS-MISSING", "Contractor termination rights not detected.", "medium", None, span))
    else:
        status, risk, score = "WARN", "high", -18
        findings.append(_mk_finding("TERM-CLAUSE-MISSING", "Termination rights not clearly stated.", "high", None, span))
    return _mk_analysis(clause_type, title or "Termination", span, status, risk, score, findings)

def _check_governing_law_disputes(text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    # Governing law
    ct_gl = "governing_law"
    title_gl, span_gl = _sec_for_clause(
        sections,
        ["governing_law", "law", "jurisdiction"],
        [r"\bgoverning law\b", r"\blaw and jurisdiction\b", r"\bjurisdiction\b"]
    )
    ctx_gl = _ctx(text, span_gl)
    has_eng = re.search(r"\b(England|English law|laws? of England(?: and Wales)?)\b", ctx_gl, re.IGNORECASE) is not None

    findings_gl: List[Dict[str, Any]] = []
    if has_eng:
        status_gl, risk_gl, score_gl = "OK", "low", 8
    else:
        status_gl, risk_gl, score_gl = "WARN", "medium", -10
        findings_gl.append(_mk_finding("GL-NO-ENGLAND", "No explicit reference to the laws of England and Wales detected.", "medium", None, span_gl))
    out.append(_mk_analysis(ct_gl, title_gl or "Governing Law", span_gl, status_gl, risk_gl, score_gl, findings_gl))

    # Dispute resolution
    ct_dr = "dispute_resolution"
    title_dr, span_dr = _sec_for_clause(
        sections,
        ["dispute_resolution", "disputes", "arbitration"],
        [r"\bdispute resolution\b", r"\barbitration\b|\bLCIA\b|\bICC\b", r"\bmediation\b"]
    )
    ctx_dr = _ctx(text, span_dr)
    has_proc = any([
        re.search(r"\bdispute resolution\b|\bdispute procedure\b", ctx_dr, re.IGNORECASE),
        re.search(r"\barbitration\b|\bLCIA\b|\bICC\b", ctx_dr, re.IGNORECASE),
        re.search(r"\bmediation\b", ctx_dr, re.IGNORECASE),
    ])
    findings_dr: List[Dict[str, Any]] = []
    if has_proc:
        status_dr, risk_dr, score_dr = "OK", "low", 8
    else:
        status_dr, risk_dr, score_dr = "WARN", "medium", -8
        findings_dr.append(_mk_finding("DR-PROCEDURE-MISSING", "No dispute resolution procedure detected (arbitration/mediation/escalation).", "medium", None, span_dr))
    out.append(_mk_analysis(ct_dr, title_dr or "Dispute Resolution", span_dr, status_dr, risk_dr, score_dr, findings_dr))

    return out

def _check_call_off(text: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    clause_type = "call_off"
    title, span = _sec_for_clause(
        sections,
        ["call_off", "orders", "ordering", "framework", "scope"],
        [r"\bcall[- ]?off\b", r"\bpurchase order\b|\bPO\b", r"\border of precedence\b", r"\bnon[- ]exclusive\b", r"\bseparate contracts?\b"]
    )
    ctx = _ctx(text, span)
    has_nonexclusive = re.search(r"\bnon[- ]exclusive\b", ctx, re.IGNORECASE) is not None
    has_calloff = re.search(r"\bcall[- ]?off\b", ctx, re.IGNORECASE) is not None
    has_separate = re.search(r"\bseparate contracts?\b|\bforms?\s+separate contract\b", ctx, re.IGNORECASE) is not None
    has_precedence = re.search(r"\border of precedence\b|\bprecedence\b", ctx, re.IGNORECASE) is not None

    findings: List[Dict[str, Any]] = []
    conds = [has_nonexclusive, has_calloff, has_separate, has_precedence]
    if all(conds):
        status, risk, score = "OK", "low", 8
    else:
        status, risk, score = "WARN", "medium", -10
        missing_msgs = []
        if not has_nonexclusive: missing_msgs.append("non-exclusive")
        if not has_calloff: missing_msgs.append("call-off")
        if not has_separate: missing_msgs.append("separate contracts")
        if not has_precedence: missing_msgs.append("order of precedence")
        findings.append(_mk_finding("CO-MISSING-ELEMS", f"Missing elements: {', '.join(missing_msgs)}.", "medium", None, span))
    return _mk_analysis(clause_type, title or "Call-Off / Ordering", span, status, risk, score, findings)

# ----------------------- aggregator -----------------------
def _aggregate(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not analyses:
        return {"summary_status": "OK", "summary_risk": "medium", "summary_score": 0}
    worst = max((_risk_to_ord(a.get("risk_level", "medium")) for a in analyses), default=1)
    any_fail = any(a.get("status") == "FAIL" for a in analyses)
    any_warn = any(a.get("status") == "WARN" for a in analyses)
    if any_fail:
        status = "FAIL"
    elif any_warn:
        status = "WARN"
    else:
        status = "OK"
    scores = [int(a.get("score", 0) or 0) for a in analyses]
    avg = int(round(sum(scores) / len(scores))) if scores else 0
    return {
        "summary_status": status,
        "summary_risk": _ord_to_risk(worst),
        "summary_score": _clamp(avg, -100, 100),
        "counts": {
            "ok": sum(1 for a in analyses if a.get("status") == "OK"),
            "warn": sum(1 for a in analyses if a.get("status") == "WARN"),
            "fail": sum(1 for a in analyses if a.get("status") == "FAIL"),
        },
    }

# ----------------------- public API -----------------------
def evaluate(text: str, sections: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    text = text or ""
    sections = list(sections or [])

    analyses: List[Dict[str, Any]] = []
    # Order is deterministic and matches typical priority in UK O&G MSA reviews
    analyses.append(_check_limitation_of_liability(text, sections))
    analyses.append(_check_anti_bribery(text, sections))
    analyses.append(_check_exhibit_L_present(text, sections))
    analyses.append(_check_exhibit_M_present(text, sections))
    analyses.append(_check_information_security(text, sections))
    analyses.append(_check_data_protection(text, sections))
    analyses.append(_check_export_control(text, sections))
    analyses.append(_check_insurance(text, sections))
    analyses.append(_check_hse(text, sections))
    analyses.append(_check_termination(text, sections))
    analyses.extend(_check_governing_law_disputes(text, sections))
    analyses.append(_check_call_off(text, sections))

    # Normalize ordering by span.start then clause_type
    analyses.sort(key=lambda a: (int(a.get("span", {}).get("start", 0)), str(a.get("clause_type", "")).lower()))
    metrics = _aggregate(analyses)
    return analyses, metrics
