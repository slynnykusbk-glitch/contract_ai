from __future__ import annotations

import hashlib
import os
import time
from typing import List, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from contract_review_app.core.schemas import (
    ExplainRequest,
    ExplainResponse,
    Citation,
    Evidence,
)
from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.privacy import redact_pii, scrub_llm_output
from contract_review_app.corpus.db import SessionLocal
from contract_review_app.retrieval.search import search_corpus
from contract_review_app.llm.citation_resolver import make_grounding_pack
from contract_review_app.llm.prompt_builder import build_prompt
from contract_review_app.llm.provider import get_provider
from contract_review_app.llm.verification import verify_output_contains_citations
from contract_review_app.core.audit import audit
from .headers import apply_std_headers
from contract_review_app.core.trace import compute_cid
from .auth import require_api_key_and_schema


router = APIRouter(prefix="/api")

_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def _env_truthy(name: str) -> bool:
    return (os.getenv(name, "") or "").strip().lower() in _TRUTHY


# instantiate provider once for explain endpoint
LLM_PROVIDER = get_provider()


_RULE_HINTS = {
    "uk_poca_tipping_off": {
        "why": "Disclosing a suspicious activity report may constitute tipping off under POCA.",
        "fix": "Include an explicit carve-out allowing disclosures required by POCA.",
    },
    "uk_ucta_2_1_invalid": {
        "why": "UCTA 1977 prohibits excluding liability for death or personal injury caused by negligence.",
        "fix": "Remove or modify the exclusion to comply with UCTA 1977.",
    },
    "uk_fraud_exclusion_invalid": {
        "why": "Liability for fraud or fraudulent misrepresentation cannot be excluded.",
        "fix": "Carve out fraud and fraudulent misrepresentation from the exclusion.",
    },
    "uk_dpa_1998_outdated": {
        "why": "References to the Data Protection Act 1998 are outdated.",
        "fix": "Update the clause to refer to the Data Protection Act 2018 or UK GDPR.",
    },
    "uk_ca_1985_outdated": {
        "why": "Companies Act 1985 has been replaced by the Companies Act 2006.",
        "fix": "Refer to the Companies Act 2006 instead.",
    },
    "uk_bribery_act_missing": {
        "why": "Anti-bribery provisions should reference the UK Bribery Act 2010.",
        "fix": "Add a reference to compliance with the Bribery Act 2010.",
    },
    "gl_jurisdiction_conflict": {
        "why": "Governing law and jurisdiction clauses are inconsistent.",
        "fix": "Align governing law with the jurisdiction clause or clarify the relationship.",
    },
}


def _deterministic_reasoning(finding, citation: Optional[Citation]) -> str:
    info = _RULE_HINTS.get(getattr(finding, "code", ""), {})
    instrument = (
        citation.instrument if citation else info.get("instrument", "")
    ) or "Unknown"
    section = (citation.section if citation else info.get("section", "")) or ""
    why = info.get("why", "Potential legal non-compliance.")
    fix = info.get("fix", "Review and amend the clause accordingly.")
    return (
        f"{finding.message}. Legal basis: {instrument} §{section}. "
        f"Why this matters: {why}. How to fix: {fix}."
    )


def _gather_evidence(citations: List[Citation]) -> List[Evidence]:
    evidence: List[Evidence] = []
    try:
        with SessionLocal() as session:
            for cit in citations:
                query = f"{cit.instrument} {cit.section}".strip()
                rows = search_corpus(session, query, top=3)
                for r in rows[:3]:
                    snippet = (r.get("snippet") or r.get("text") or "")[:320]
                    evidence.append(
                        Evidence(text=snippet, source=cit.instrument, link=cit.url)
                    )
    except Exception:
        return []
    return evidence


@router.post(
    "/explain",
    response_model=ExplainResponse,
    dependencies=[Depends(require_api_key_and_schema)],
)
async def api_explain(body: ExplainRequest, request: Request) -> JSONResponse:
    started = time.perf_counter()
    cid = getattr(request.state, "cid", compute_cid(request))

    text = body.text or ""
    doc_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None

    finding = body.finding
    citations = body.citations or []
    if not citations:
        cit = resolve_citation(finding)
        if cit:
            citations = [cit]

    evidence = _gather_evidence(citations)

    context = ""
    if text and getattr(finding, "span", None):
        span = finding.span
        end_pos = span.start + (getattr(span, "length", 0) or 0)
        start = max(0, span.start - 400)
        end = min(len(text), end_pos + 400)
        context = text[start:end]

    redacted_context, pii_map = redact_pii(context)

    grounding = make_grounding_pack(
        finding.message, redacted_context, [c.model_dump() for c in citations]
    )

    use_llm = _env_truthy("FEATURE_LLM_EXPLAIN")
    reasoning = ""
    verification_status = "ok"

    if use_llm:
        try:
            prompt = build_prompt("explain", grounding)
            res = LLM_PROVIDER.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                top_p=1.0,
            )
            llm_reasoning = scrub_llm_output(res.get("content", ""), pii_map)
            v = verify_output_contains_citations(
                llm_reasoning, grounding.get("evidence", [])
            )
            if v == "verified":
                reasoning = llm_reasoning
                verification_status = "ok"
            else:
                verification_status = "missing_citations"
                reasoning = _deterministic_reasoning(
                    finding, citations[0] if citations else None
                )
        except Exception:
            verification_status = "invalid"
            reasoning = _deterministic_reasoning(
                finding, citations[0] if citations else None
            )
    else:
        reasoning = _deterministic_reasoning(
            finding, citations[0] if citations else None
        )

    reasoning = scrub_llm_output(reasoning, pii_map)

    resp_obj = ExplainResponse(
        reasoning=reasoning,
        citations=citations,
        evidence=evidence,
        verification_status=verification_status,
        trace=cid,
    )

    resp = JSONResponse(resp_obj.model_dump(by_alias=True))
    apply_std_headers(resp, request, started)
    resp.headers["x-cache"] = "miss"

    audit(
        "explain",
        request.headers.get("x-user"),
        doc_hash,
        {
            "citations_count": len(citations),
            "evidence_count": len(evidence),
            "rule_code": getattr(finding, "code", ""),
            "cid": cid,
        },
    )

    return resp
