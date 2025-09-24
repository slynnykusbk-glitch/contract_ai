from __future__ import annotations
import pytest

from contract_review_app.engine import pipeline
from contract_review_app.engine import pipeline_compat


def _sample_text() -> str:
    # Synthetic UK O&G MSA-like document with ALLCAPS headings so matcher can detect sections.
    parts = [
        "LIMITATION OF CONTRACTOR LIABILITY\n"
        "The aggregate liability shall be capped at £1,000,000 per occurrence and in the aggregate. "
        "Carve-outs include CONFIDENTIALITY breaches, IP INFRINGEMENT, BRIBERY, PERSONAL INJURY, and DATA PROTECTION obligations.\n",
        "APPLICABLE LAWS, ETHICS AND ANTI-BRIBERY (BRIBERY ACT 2010)\n"
        "The Parties shall comply with the UK BRIBERY ACT 2010 and anti-corruption laws.\n",
        "DATA PROTECTION (UK GDPR)\n"
        "The Parties shall comply with UK GDPR and the Data Protection Act 2018. See EXHIBIT M – DATA PROTECTION.\n",
        "EXPORT CONTROL COMPLIANCE (IMPORTER OF RECORD/EXPORTER OF RECORD)\n"
        "Supplier shall comply with export control and trade sanctions. The IMPORTER OF RECORD and EXPORTER OF RECORD are defined herein.\n",
        "HEALTH, SAFETY, AND ENVIRONMENT\n"
        "Contractor must comply with HSE REQUIREMENTS and COMPANY LIFE SAVING RULES. Offshore exhibits (EXHIBIT A/E/F) apply.\n",
        "TERMINATION AND SUSPENSION\n"
        "Company may terminate for convenience with notice. Contractor may terminate for non-payment or material breach by Company.\n",
        "CALL-OFF PROCESS\n"
        "This is a non-exclusive framework. Each call-off forms a separate contract. The order of precedence is specified herein.\n",
        "GOVERNING LAW\n"
        "This Agreement is governed by the laws of England and Wales. Dispute resolution procedure may include arbitration under LCIA rules.\n",
    ]
    return "\n".join(parts)


def test_detect_core_clauses_and_metrics():
    text = _sample_text()
    ssot = pipeline.analyze_document(text)
    analysis, results, clauses = pipeline_compat.to_panel_shape(ssot)

    # Expected clause types present in results (keys come from rule analyses)
    expected = {
        "limitation_of_liability",
        "anti_bribery",
        "data_protection",
        "export_control",
        "hse",
        "termination",
        "call_off",
        "governing_law",
    }

    assert isinstance(results, dict)
    missing = expected.difference(set(results.keys()))
    assert not missing, f"Missing result buckets: {missing}"

    assert isinstance(analysis, dict)
    assert analysis.get("status") in {"OK", "WARN", "FAIL"}
    assert isinstance(analysis.get("score"), int)


def test_suggest_edits_by_clause_type():
    text = _sample_text()
    suggestions = pipeline.suggest_edits(
        text, clause_id=None, mode="friendly", clause_type="limitation_of_liability"
    )

    assert (
        isinstance(suggestions, list) and suggestions
    ), "Expected non-empty suggestions list"
    s0 = suggestions[0]
    assert (
        "message" in s0
        and isinstance(s0["message"], str)
        and s0["message"].strip() != ""
    )
    rng = s0.get("range")
    assert isinstance(rng, dict), "range must be a dict"
    assert isinstance(rng.get("start"), int) and rng["start"] >= 0
    assert isinstance(rng.get("length"), int) and rng["length"] >= 0
