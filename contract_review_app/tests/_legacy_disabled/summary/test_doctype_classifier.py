import pytest

from contract_review_app.analysis.extract_summary import extract_document_snapshot

CASES = [
    (
        "NDA",
        """NON-DISCLOSURE AGREEMENT\nConfidential Information shall be used only for the Permitted Purpose by the Disclosing Party and the Receiving Party and must be returned or destroyed.""",
    ),
    (
        "MSA (Services)",
        """MASTER SERVICES AGREEMENT\nServices shall be performed under each Statement of Work and subject to the Service Levels and Change Control with Acceptance criteria.""",
    ),
    (
        "Supply of Goods",
        """SUPPLY OF GOODS AGREEMENT\nDelivery terms and risk and title are defined with Incoterms and Specifications including defects and returns.""",
    ),
    (
        "DPA",
        """DATA PROCESSING AGREEMENT\nThe Controller and Processor comply with UK GDPR, protect Data Subject rights and manage sub-processor international transfers as in Annex.""",
    ),
    (
        "License (IP)",
        """IP LICENCE AGREEMENT\nThe Licensor grants the Licensee a royalty bearing licence with defined Territory and IP ownership retained.""",
    ),
    (
        "SPA (Shares)",
        """SHARE PURCHASE AGREEMENT\nSeller and Buyer agree to the sale of the entire issued share capital with Completion, Disclosure Letter and Warranties and indemnities.""",
    ),
    (
        "Employment",
        """EMPLOYMENT AGREEMENT\nThe Employer engages the Employee with salary, probationary period, notice period and holiday entitlement.""",
    ),
    (
        "Loan",
        """LOAN AGREEMENT\nThe Borrower receives the principal with an interest rate and repayment terms; events of default and security apply.""",
    ),
    (
        "Lease",
        """LEASE AGREEMENT\nThe Landlord lets the premises to the Tenant for a term with rent and repair and insurance obligations.""",
    ),
    (
        "SaaS Subscription",
        """SAAS SUBSCRIPTION AGREEMENT\nSubscription to the cloud service includes availability uptime commitments, support and user licences.""",
    ),
]


@pytest.mark.parametrize("expected,text", CASES)
def test_doctype_classifier(expected: str, text: str):
    snap = extract_document_snapshot(text)
    assert snap.type == expected
    assert snap.type_confidence >= 0.6
    assert len(snap.hints) >= 1
