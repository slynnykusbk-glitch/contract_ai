from __future__ import annotations

"""Heuristic document type classifier."""

from typing import Dict, List, Tuple

from .patterns_doctype import DOC_TYPE_PATTERNS

W_TITLE = 0.4
W_BODY = 0.6

DISPLAY_MAP = {
    "nda": "NDA",
    "msa_services": "MSA (Services)",
    "supply_of_goods": "Supply of Goods",
    "dpa_uk_gdpr": "DPA",
    "license_ip": "License (IP)",
    "distribution": "Distribution",
    "reseller": "Reseller",
    "spa_shares": "SPA (Shares)",
    "employment": "Employment",
    "loan": "Loan",
    "lease": "Lease",
    "saas_subscription": "SaaS Subscription",
    "consultancy": "Consultancy",
    "settlement": "Settlement",
    "shareholders": "Shareholders",
    "joint_venture": "Joint Venture",
    "framework_calloff": "Framework Call-Off",
    "manufacturing": "Manufacturing",
    "maintenance_support": "Maintenance & Support",
}


def slug_to_display(slug: str) -> str:
    return DISPLAY_MAP.get(slug, slug.replace("_", " ").title())


def _match_keywords(haystack: str, keywords: List[str]) -> Tuple[int, List[str]]:
    hits: List[str] = []
    cnt = 0
    for kw in keywords:
        if kw and kw.lower() in haystack:
            cnt += 1
            hits.append(kw)
    return cnt, hits


def guess_doc_type(text: str) -> Tuple[str, float, List[str], Dict[str, float]]:
    """Return (slug, confidence, evidence_strings, score_by_type)."""
    t = text or ""
    # normalize text
    lowered = t.lower()
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    title = " ".join(lines[:2]).lower()

    score_raw: Dict[str, float] = {}
    evidences: Dict[str, List[str]] = {}

    for slug, cfg in DOC_TYPE_PATTERNS.items():
        title_hits, title_ev = _match_keywords(title, cfg.get("title_keywords", []))
        body_hits, body_ev = _match_keywords(lowered, cfg.get("body_keywords", []))
        boost = 0.0
        boost_ev: List[str] = []
        for phrase, weight in cfg.get("boost_phrases", {}).items():
            if phrase.lower() in lowered:
                boost += float(weight)
                boost_ev.append(phrase)
        score = W_TITLE * title_hits + W_BODY * (body_hits + boost)
        must_any = cfg.get("must_have_any")
        if must_any and not any(m.lower() in lowered for m in must_any):
            score = 0.0
        negative = cfg.get("negative")
        if negative and any(n.lower() in lowered for n in negative):
            score = 0.0
        score_raw[slug] = score
        evidences[slug] = title_ev + body_ev + boost_ev

    max_score = max(score_raw.values()) if score_raw else 0.0
    score_by_type: Dict[str, float] = {}
    for slug, sc in score_raw.items():
        score_by_type[slug] = sc / max_score if max_score else 0.0
    best_slug = max(score_raw, key=score_raw.get) if score_raw else "unknown"
    confidence = score_by_type.get(best_slug, 0.0)
    evidence = evidences.get(best_slug, [])
    return best_slug, round(confidence, 2), evidence, score_by_type

