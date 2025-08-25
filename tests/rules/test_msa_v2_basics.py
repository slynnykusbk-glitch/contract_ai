import json
from typing import List

from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.legal_rules.loader import rules_count

client = TestClient(app)


def _analyze(text: str) -> List[dict]:
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    return resp.json()["analysis"]["findings"]


def test_rules_count_at_least_30():
    assert rules_count() >= 30


_cases = [
    (
        "confidentiality_survival_term_min_3y",
        "confidentiality",
        "Confidentiality obligations survive for 3 years after termination.",
        "Confidentiality obligations survive for 1 year after termination.",
    ),
    (
        "confidentiality_exceptions",
        "confidentiality",
        "Information already known, independently developed or legally compelled may be disclosed and injunctive relief is available.",
        "No exceptions to confidentiality obligations are permitted.",
    ),
    (
        "audit_rights_scope_retention",
        "audit",
        "Company may audit Supplier's books on five business days' notice and records must be kept for seven years.",
        "Supplier's records are private and cannot be reviewed by the Company.",
    ),
    (
        "notices_formal_service",
        "notices",
        "Notices may be served by post, courier or email/PDF to the named addresses and are effective on delivery.",
        "Parties will communicate informally without any notice procedure.",
    ),
    (
        "assignment_consent_exceptions",
        "assignment",
        "Supplier may assign to an Affiliate or upon change of control with notice and consent not unreasonably withheld.",
        "Supplier must perform the work itself without delegation.",
    ),
    (
        "ip_ownership_licenseback",
        "intellectual_property",
        "All Foreground IP shall belong to Company; Supplier retains its Background IP with a license-back only to perform the Services.",
        "Supplier retains ownership of all IP developed under this Agreement without any license back to Company.",
    ),
    (
        "force_majeure_exclusions",
        "force_majeure",
        "Force majeure does not excuse payment obligations or strikes by Supplier's workforce and parties must mitigate with termination after 60 days.",
        "Any event whatsoever excuses all obligations without mitigation or termination rights.",
    ),
    (
        "governing_law_e_wales_cisg_excluded",
        "governing_law",
        "This Agreement is governed by the laws of England and Wales and the UN CISG is excluded.",
        "Governing law is unspecified and CISG applies by default.",
    ),
    (
        "variation_change_control",
        "change_control",
        "Any amendments must follow the Change Control procedure and be documented in a Variation Order.",
        "Parties may change the scope informally without documentation.",
    ),
    (
        "placeholder_police",
        "placeholder",
        "Payment date [●] is a placeholder and must be completed.",
        "The clause contains no placeholders.",
    ),
]


import pytest


@pytest.mark.parametrize("rule_id, clause_type, positive, negative", _cases)
def test_examples(rule_id: str, clause_type: str, positive: str, negative: str):
    findings_pos = _analyze(positive)
    assert any(f["rule_id"] == rule_id and f["clause_type"] == clause_type for f in findings_pos)

    findings_neg = _analyze(negative)
    assert all(f["rule_id"] != rule_id for f in findings_neg)
