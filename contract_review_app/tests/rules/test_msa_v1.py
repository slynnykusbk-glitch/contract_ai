from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.legal_rules import loader

client = TestClient(app)


def test_rules_count_minimum():
    assert loader.rules_count() >= 20


SAMPLES = [
    ("governing_law", "governing_law",
     "This Agreement is governed by the laws of England and Wales and excludes the United Nations Convention on Contracts for the International Sale of Goods.",
     "This Agreement is governed by Texas law."),
    ("dispute_resolution", "dispute_resolution",
     "A Dispute Notice shall be issued and the parties agree to the exclusive jurisdiction of the courts of England and Wales.",
     "Disputes may be brought anywhere."),
    ("termination_cause", "termination",
     "Company may terminate for cause. Mobilisation fees refunded to Company.",
     "Company may terminate for cause."),
    ("termination_convenience", "termination",
     "Company may terminate for convenience and Contractor shall receive no anticipatory profit.",
     "Company may terminate for convenience and recover its costs."),
    ("liability_cap", "limitation_of_liability",
     "Liability is capped at £1m and does not apply to HSE, Taxes or IP obligations.",
     "Liability is limited to £1m."),
    ("insurance_noncompliance", "insurance",
     "Contractor shall name Company as an additional insured and failure to maintain insurance shall entitle Company to terminate.",
     "Contractor shall maintain insurance."),
    ("export_hmrc", "export_control",
     "Contractor is the Exporter of Record and shall comply with HMRC procedures.",
     "Contractor is the Exporter of Record."),
    ("placeholder_police", "placeholders",
     "The price is [●] per unit.",
     "The price is fixed."),
]


def _match(text: str, clause_type: str) -> bool:
    return any(f.get("clause_type") == clause_type for f in loader.match_text(text))


def test_positive_negative_samples():
    for _id, clause_type, pos, neg in SAMPLES:
        assert _match(pos, clause_type)
        assert not _match(neg, clause_type)


def test_placeholder_detection():
    assert _match("A cost of [DELETE AS APPROPRIATE] applies.", "placeholders")


def test_analyze_endpoint_returns_findings():
    text = SAMPLES[0][2]
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    data = r.json()
    findings = data.get("analysis", {}).get("findings", [])
    assert findings and all(f.get("clause_type") for f in findings)
