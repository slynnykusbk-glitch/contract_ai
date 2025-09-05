import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def test_identity_positive():
    spec = load_rule("core/rules/uk/parties/01_identity.yaml")
    text = "Chrysaor Production (U.K.) Limited (Company No. 00524868), a company incorporated in England and Wales with registered office in London."
    out = run_rule(spec, AnalysisInput(clause_type="preamble", text=text,
                                       metadata={"jurisdiction":"UK","doc_type":"Master Agreement"}))
    assert out is None or len(out.findings) == 0

def test_identity_negative_placeholder():
    spec = load_rule("core/rules/uk/parties/01_identity.yaml")
    text = "[●] Contractor, a company incorporated in [●] with registered office at PO Box 123"
    out = run_rule(spec, AnalysisInput(clause_type="preamble", text=text,
                                       metadata={"jurisdiction":"UK","doc_type":"Master Agreement"}))
    assert out is not None
    assert any("placeholder" in f.message.lower() or "Company number" in f.message for f in out.findings)
    assert out.risk_level in ("medium","high")
