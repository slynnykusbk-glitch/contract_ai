from contract_review_app.legal_rules.rules import registry, list_rule_names


def test_registry_contains_expected_rules():
    """The registry should expose canonical rule names and common aliases."""

    expected = {
        "governing_law",
        "jurisdiction",
        "indemnity",
        "confidentiality",
        "definitions",
        "termination",
        "force_majeure",
        "oilgas_master_agreement",
        # aliases
        "non_disclosure",
        "dispute_resolution",
    }

    for key in expected:
        assert key in registry, f"missing {key} in registry"

    # alias mapping should point at the same callable
    assert registry["non_disclosure"] is registry["confidentiality"]
    assert registry["dispute_resolution"] is registry["jurisdiction"]

    # list_rule_names should include canonical entries
    names = list_rule_names()
    assert "governing_law" in names and "non_disclosure" in names

    # every registry entry must be callable
    for func in registry.values():
        assert callable(func)
