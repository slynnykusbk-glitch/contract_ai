from __future__ import annotations

import re

import pytest

try:
    from hypothesis import given, strategies as st
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    given = None
    st = None

from contract_review_app.analysis import LABELS_CANON, resolve_labels


@pytest.mark.parametrize(
    "label, token",
    [
        (label, synonym)
        for label, config in LABELS_CANON.items()
        for synonym in config.get("high_priority_synonyms", [])
        if isinstance(synonym, str) and synonym
    ],
)
def test_resolve_labels_positive_from_heading(label: str, token: str) -> None:
    result = resolve_labels("", token)
    assert label in result


@pytest.mark.parametrize(
    "label, token",
    [
        (label, synonym)
        for label, config in LABELS_CANON.items()
        for synonym in config.get("high_priority_synonyms", [])
        if isinstance(synonym, str) and synonym
    ],
)
def test_resolve_labels_negative_from_scrambled_text(label: str, token: str) -> None:
    scrambled = " ".join(token)
    result = resolve_labels(scrambled, None)
    assert label not in result


@pytest.mark.parametrize(
    "label, token",
    [
        (label, synonym)
        for label, config in LABELS_CANON.items()
        for synonym in config.get("high_priority_synonyms", [])
        if isinstance(synonym, str) and synonym
    ],
)
def test_resolve_labels_positive_from_body(label: str, token: str) -> None:
    body = f"Intro section. {token} applies to the obligations."
    result = resolve_labels(body, None)
    assert label in result


def test_payment_terms_regex_variants() -> None:
    assert "payment_terms" in resolve_labels(
        "Invoices are due net thirty (30) days from receipt.", None
    )
    assert "payment_terms" in resolve_labels(
        "Payment must occur within sixty (60) business days of acceptance.", None
    )


@pytest.mark.parametrize(
    "text, expected_label",
    [
        ("Interest will be base rate + 4% until paid.", "late_payment_interest"),
        ("The aggregate liability cap is £1,200,000 per Contract Year.", "liability_cap_amount"),
        (
            "The applicable delivery terms follow the DDP Incoterm for 2020.",
            "delivery_terms_incoterms",
        ),
    ],
)
def test_regex_patterns(text: str, expected_label: str) -> None:
    assert expected_label in resolve_labels(text, None)


def test_analysis_window_includes_tail() -> None:
    filler = "x" * 1200
    tail = "Service Level Agreement metrics shall apply."
    text = filler + tail
    result = resolve_labels(text, None)
    assert "service_levels_sla" in result


if st is not None:

    @st.composite
    def _typography_variants(draw):
        eligible = [
            (label, [token for token in cfg.get("high_priority_synonyms", []) if token])
            for label, cfg in LABELS_CANON.items()
        ]
        eligible = [(label, tokens) for label, tokens in eligible if tokens]
        label, tokens = draw(st.sampled_from(eligible))
        token = draw(st.sampled_from(tokens))

        def mutate_char(ch: str) -> str:
            replacements = {
                " ": [" ", "\u00A0"],
                "-": ["-", "\u2013", "\u2014"],
                "'": ["'", "\u2018", "\u2019"],
                '"': ['"', "\u201c", "\u201d"],
            }
            options = replacements.get(ch, [ch])
            return draw(st.sampled_from(options))

        mutated = "".join(mutate_char(ch) for ch in token)

        if any(ch.isdigit() for ch in token) and draw(st.booleans()):
            mutated = re.sub(r"(\d+)", r"(\1)", mutated, count=1)

        return label, mutated


    @given(_typography_variants())
    def test_resolve_labels_typography_invariance(data: tuple[str, str]) -> None:
        label, sample = data
        result = resolve_labels("", sample)
        assert label in result

else:  # pragma: no cover - executed only when hypothesis is missing

    def test_resolve_labels_typography_invariance() -> None:
        pytest.skip("hypothesis not installed")


def test_resolve_labels_empty_input() -> None:
    assert resolve_labels("", None) == set()
