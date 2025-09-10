import random
import re

import pytest

from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules import governing_law as gl


# --- утиліти для варіацій без залежності від зовнішніх ресурсів ---
def _noise(s: str) -> str:
    # додаємо випадкові пробіли/переноси та зміну регістру в межах тесту
    s = re.sub(r"\s+", " ", s)
    s = "".join(ch.upper() if random.random() < 0.2 else ch for ch in s)
    s = "  ".join(s.split(" "))
    return s


def _mk_input(txt: str) -> AnalysisInput:
    return AnalysisInput(
        clause_type="governing_law", text=txt, metadata={"t": "property"}
    )


# Спроба використати Hypothesis, якщо встановлено; якщо ні — скіп.
hypothesis = pytest.importorskip(
    "hypothesis", reason="property tests require hypothesis"
)
from hypothesis import given, strategies as st


@given(
    st.sampled_from(
        [
            "This Agreement shall be governed by the laws of England and Wales, excluding its conflict of laws rules.",
            "Цей договір регулюється правом України, без урахування колізійних норм.",
            "This contract is governed by the laws of Scotland.",
        ]
    )
)
def test_property_variants_still_detect_governing_law(base):
    var = _noise(base)
    out = gl.analyze(_mk_input(var))

    # має бути OK або WARN (принаймні не FAIL, бо згадка про право присутня)
    assert out.status in {"OK", "WARN"}
    # має бути знайдений слід у trace і посилання
    assert gl.RULE_NAME == out.diagnostics.get("rule")
    assert isinstance(out.diagnostics.get("citations", ""), str)


@given(st.integers(min_value=0, max_value=3))
def test_property_jurisdiction_only_warn(n):
    bases = [
        "The parties submit to the non-exclusive jurisdiction of the courts of England.",
        "Сторони підсудні судам України.",
        "Venue is London. Courts of Scotland shall have exclusive jurisdiction.",
        "Сторони погоджуються на виключну підсудність судів Англії та Уельсу.",
    ]
    var = _noise(bases[n])
    out = gl.analyze(_mk_input(var))
    assert out.status == "WARN"
