import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput


def ai(text, clause="recitals"):
    return AnalysisInput(
        clause_type=clause,
        text=text,
        metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
    )


def test_r1_no_min_purchase_positive():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/01_recitals_no_minimum_purchase.yaml"
    )
    out = run_rule(
        spec, ai("Recitals: The parties intend to transact under Call-Offs.")
    )
    assert out is None or len(getattr(out, "findings", [])) == 0


def test_r1_no_min_purchase_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/01_recitals_no_minimum_purchase.yaml"
    )
    out = run_rule(
        spec,
        ai("In Recitals, Contractor shall purchase at least 10,000 units per year."),
    )
    assert out is not None and any(
        "minimum" in f.message.lower() or "volume" in f.message.lower()
        for f in out.findings
    )


def test_r2_no_operational_shall_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/02_recitals_no_operational_shall.yaml"
    )
    out = run_rule(spec, ai("Recitals: Contractor shall perform services."))
    assert out is not None and any("shall" in f.message.lower() for f in out.findings)


def test_r3_placeholders_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/03_incorp_placeholders_clean.yaml"
    )
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="1.1",
            text="Exhibit J [Amend prior to issuing externally]",
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "placeholder" in f.message.lower() or "editorial" in f.message.lower()
        for f in out.findings
    )


def test_r4_heavy_terms_notice_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/04_incorp_heavy_terms_notice.yaml"
    )
    text = "By reference are incorporated Supplier Policies, including limitation of liability and indemnity terms."
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="1.1",
            text=text,
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "heavy" in f.message.lower() or "ucta" in f.message.lower()
        for f in out.findings
    )


def test_r5_dynamic_refs_change_control_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/05_incorp_dynamic_refs_change_control.yaml"
    )
    text = "Standards shall apply as may be updated from time to time."
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="1.1",
            text=text,
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "change control" in f.message.lower() or "dynamic" in f.message.lower()
        for f in out.findings
    )


def test_r6_exhibitj_deed_formalities_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/06_exhibitj_deed_formalities.yaml"
    )
    text = "Exhibit J: Parent Company Guarantee executed as a deed by authorised signatory."
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="exhibit_j",
            text=text,
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "deed" in f.message.lower() or "s.44" in f.message.lower() for f in out.findings
    )


def test_r7_term_extensions_notices_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/07_term_extensions_notices.yaml"
    )
    text = "The Company may extend the Term."
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="1.2",
            text=text,
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "notice" in f.message.lower() or "term" in f.message.lower()
        for f in out.findings
    )


def test_r8_supplemental_priority_negative():
    spec = load_rule(
        "core/rules/uk/master/recitals_and_clauses1/08_supplemental_docs_priority.yaml"
    )
    text = "After expiry, any Purchase Order shall continue to apply and shall prevail over this Agreement."
    out = run_rule(
        spec,
        AnalysisInput(
            clause_type="1.3",
            text=text,
            metadata={"jurisdiction": "UK", "doc_type": "Master Agreement"},
        ),
    )
    assert out is not None and any(
        "precedence" in f.message.lower() or "override" in f.message.lower()
        for f in out.findings
    )
