import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def AI(text, clause="definitions", doc="Master Agreement"):
    return AnalysisInput(clause_type=clause, text=text, metadata={"jurisdiction":"UK","doc_type":doc})

# 1) BIPR
def test_bipr_negative_no_licence_and_boundary():
    spec = load_rule("core/rules/uk/definitions/b_block/01_bipr_perimeter_and_license.yaml")
    t = "Background Intellectual Property includes all IP and modifications. Foreground shall include all created during the Work."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_bipr_positive_clear_boundary_and_licence():
    spec = load_rule("core/rules/uk/definitions/b_block/01_bipr_perimeter_and_license.yaml")
    t = ("Foreground excludes Background Intellectual Property. Company has a perpetual, worldwide, royalty-free licence "
         "to use, maintain, modify and integrate BIPR within the Company Group.")
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 2) Bribe
def test_bribe_negative_missing_ukba7_poca_fcpa_flowdown():
    spec = load_rule("core/rules/uk/definitions/b_block/02_bribe_ukba_poca_fcpa.yaml")
    t = "Bribe means any improper payment under applicable anti-corruption laws."
    out = run_rule(spec, AI(t, clause="definitions"))
    assert out is not None and any("ukba coverage weak" in f.message.lower() or "poca" in f.message.lower() or "flow-down" in (f.suggestion.text.lower() if getattr(f, 'suggestion', None) else "") for f in out.findings)

def test_bribe_positive_full_coverage():
    spec = load_rule("core/rules/uk/definitions/b_block/02_bribe_ukba_poca_fcpa.yaml")
    t = ("Anti-Bribery Laws include the UK Bribery Act 2010 (including section 7 failure to prevent and adequate procedures), "
         "POCA 2002 and the US FCPA (books and records/internal controls), with flow-down to associated persons and audit/termination rights; "
         "facilitation payments are prohibited.")
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 3) Business Day
def test_business_day_negative_generic():
    spec = load_rule("core/rules/uk/definitions/b_block/03_business_day_precision.yaml")
    t = "Business Day means any day other than Saturday or Sunday."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_business_day_positive_precise():
    spec = load_rule("core/rules/uk/definitions/b_block/03_business_day_precision.yaml")
    t = ("Business Day means a day other than Saturday, Sunday or a public holiday in England and Wales "
         "(under the Banking and Financial Dealings Act 1971); ends at 17:00 UK time; references Clause 29 for deemed receipt.")
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 4) Call-Off — exclusion/precedence
def test_calloff_negative_no_exclusion_or_precedence():
    spec = load_rule("core/rules/uk/calloff/01_calloff_exclude_other_terms.yaml")
    t = "A Call-Off Order may apply with the Contractor’s terms."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any("exclusion" in f.message.lower() or "precedence" in f.message.lower() for f in out.findings)

def test_calloff_positive_exclusion_and_precedence():
    spec = load_rule("core/rules/uk/calloff/01_calloff_exclude_other_terms.yaml")
    t = "Each Call-Off excludes all other terms and conditions (including Contractor terms) and is subject to Clause 2.2 (Order of Precedence)."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 5) Call-Off — formation by performance
def test_calloff_negative_performance_no_controls():
    spec = load_rule("core/rules/uk/calloff/02_calloff_formation_by_performance_controls.yaml")
    t = "A Call-Off becomes effective upon commencement of Work."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any("acceptance by performance" in f.message.lower() or "precedence" in (f.suggestion.text.lower() if getattr(f, 'suggestion', None) else "") for f in out.findings)

def test_calloff_positive_performance_with_controls():
    spec = load_rule("core/rules/uk/calloff/02_calloff_formation_by_performance_controls.yaml")
    t = "A Call-Off may be accepted by performance, provided it excludes all other terms and is subject to Clause 2.2 (Order of Precedence)."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 6) Call-Off — minimum content
def test_calloff_negative_minimum_content():
    spec = load_rule("core/rules/uk/calloff/03_calloff_minimum_content.yaml")
    t = "Call-Off means an order issued by the Company."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any("minimum elements" in f.message.lower() for f in out.findings)

def test_calloff_positive_minimum_content():
    spec = load_rule("core/rules/uk/calloff/03_calloff_minimum_content.yaml")
    t = "Each Call-Off identifies the parties, describes the Work, sets the price/rates and includes a schedule."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0
