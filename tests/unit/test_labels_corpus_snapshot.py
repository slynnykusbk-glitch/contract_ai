from __future__ import annotations

from pathlib import Path

import pytest

from contract_review_app.analysis import resolve_labels


CORPUS_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"

CORPUS_SNAPSHOT: dict[str, dict[str, object]] = {
    "nhs_liability.txt": {
        "heading": "Limitation of Liability",
        "expected": {
            "liability_cap_amount",
            "liability_carveouts",
            "indemnity_general",
            "limitation_of_liability",
        },
    },
    "msc_service_levels.txt": {
        "heading": "Service Levels",
        "expected": {
            "parties",
            "service_levels_sla",
            "service_credits",
            "support_maintenance",
            "term",
            "warranty_doas_rma",
        },
    },
    "idta_transfers.txt": {
        "heading": "International Data Transfers",
        "expected": {
            "dp_breach_notification",
            "dp_international_transfers",
            "dp_roles",
            "dp_security_measures",
            "hazardous_substances",
            "parties",
        },
    },
    "ast_employment.txt": {
        "heading": "Employment Matters",
        "expected": {
            "joa_authorisation_for_expenditure",
            "health_and_safety",
            "parties",
            "staff_vetting",
            "tupe",
        },
    },
    "joa_governance.txt": {
        "heading": "Joint Operating Committee",
        "expected": {
            "construction_programme",
            "dp_lawful_basis",
            "joa_authorisation_for_expenditure",
            "joa_default_nonconsent",
            "joa_opcom",
            "joa_operator",
            "joa_work_program_budget",
            "parties",
        },
    },
    "po_payment.txt": {
        "heading": "Payment Terms",
        "expected": {
            "late_payment_interest",
            "payment_terms",
            "set_off",
            "term",
        },
    },
}


@pytest.mark.parametrize("filename", sorted(CORPUS_SNAPSHOT))
def test_labels_corpus_snapshot(filename: str) -> None:
    config = CORPUS_SNAPSHOT[filename]
    heading = config["heading"]
    expected = set(config["expected"])

    text = (CORPUS_ROOT / filename).read_text(encoding="utf-8")
    resolved = resolve_labels(text, heading)

    assert resolved == expected
