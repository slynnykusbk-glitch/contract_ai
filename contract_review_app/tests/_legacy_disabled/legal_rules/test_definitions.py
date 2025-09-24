from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import definitions as defs


def test_definitions_empty_or_weak_clause_warn_or_fail():
    inp = AnalysisInput(
        clause_type="definitions",
        text="This section provides introductory information only.",
    )
    out = defs.analyze(inp)
    assert out.status in {"WARN", "FAIL"}
    assert out.category == "definitions"
    assert isinstance(out.findings, list)
    assert isinstance(out.recommendations, list)
    assert isinstance(out.trace, list)


def test_definitions_reasonable_ok_or_warn():
    text = """
    DEFINITIONS AND INTERPRETATION
    "Agreement" means this agreement between the parties.
    "Services" means the services described in Schedule 1.
    ABC Ltd (the "Supplier") and XYZ LLP (the "Customer") are collectively the "Parties".
    """
    out = defs.analyze(AnalysisInput(clause_type="definitions", text=text))
    # Якщо все ок – OK; якщо дрібні зауваження форматування – WARN, але не FAIL
    assert out.status in {"OK", "WARN"}
    assert out.score >= 65
