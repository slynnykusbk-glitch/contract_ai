import pytest
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules import (
    termination,
    indemnity,
    confidentiality,
    jurisdiction,
    force_majeure,
)


def _inp(txt, ct):
    return AnalysisInput(clause_type=ct, text=txt, metadata={"t": "prop"})


# --- прості юніт-сценарії ---
def test_termination_minimal_ok_warn():
    ok_txt = "Either party may terminate for cause upon material breach with a 30 days cure period and 10 days notice. Survives confidentiality."
    out = termination.analyze(_inp(ok_txt, "termination"))
    assert out.status in {"OK", "WARN"}

    warn_txt = "Party may terminate for convenience."
    out2 = termination.analyze(_inp(warn_txt, "termination"))
    assert out2.status in {"WARN", "OK"}


def test_indemnity_presence_and_carveouts():
    txt = "Supplier shall indemnify and hold harmless Customer against any third party claims and defence costs, except for fraud or gross negligence."
    out = indemnity.analyze(_inp(txt, "indemnity"))
    assert out.status in {"OK", "WARN"}


def test_confidentiality_presence():
    txt = "Confidential Information means any non-public data. Exclusions include information in the public domain or independently developed. Use only for the project on a need-to-know basis for 3 years after termination."
    out = confidentiality.analyze(_inp(txt, "confidentiality"))
    assert out.status in {"OK", "WARN"}


def test_jurisdiction_presence():
    txt = "The courts of England shall have exclusive jurisdiction. Service of process shall be effected by courier."
    out = jurisdiction.analyze(_inp(txt, "jurisdiction"))
    assert out.status in {"OK", "WARN"}


def test_force_majeure_presence():
    txt = "Neither party shall be liable for delay due to Force Majeure such as war, epidemic, governmental acts. Notice within 10 days, parties shall mitigate. If the event continues 60 days, either party may terminate."
    out = force_majeure.analyze(_inp(txt, "force_majeure"))
    assert out.status in {"OK", "WARN"}


# --- property (якщо є hypothesis) ---
hypothesis = pytest.importorskip(
    "hypothesis", reason="property tests require hypothesis"
)
from hypothesis import given, strategies as st


@given(st.text(min_size=50, max_size=120).map(lambda s: "terminate " + s))
def test_prop_termination_no_crash(s):
    out = termination.analyze(_inp(s, "termination"))
    assert out.status in {"OK", "WARN", "FAIL"}


@given(st.text(min_size=50, max_size=120).map(lambda s: "indemnify " + s))
def test_prop_indemnity_no_crash(s):
    out = indemnity.analyze(_inp(s, "indemnity"))
    assert out.status in {"OK", "WARN", "FAIL"}
