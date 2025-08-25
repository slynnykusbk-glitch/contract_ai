import pathlib
import pytest
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import governing_law

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "msa_v1"
RULES = {
    "governing_law": governing_law,
}

@pytest.mark.parametrize("rule_name", list(RULES.keys()))
def test_rule_positive(rule_name):
    text = (FIXTURES / f"{rule_name}_positive.txt").read_text()
    mod = RULES[rule_name]
    out = mod.analyze(AnalysisInput(clause_type=rule_name, text=text))
    assert out.status == "OK"

@pytest.mark.parametrize("rule_name", list(RULES.keys()))
def test_rule_negative(rule_name):
    text = (FIXTURES / f"{rule_name}_negative.txt").read_text()
    mod = RULES[rule_name]
    out = mod.analyze(AnalysisInput(clause_type=rule_name, text=text))
    assert out.status != "OK"


def test_health_rules_count():
    from fastapi.testclient import TestClient
    from contract_review_app.api.app import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("rules_count", 0) >= 30
