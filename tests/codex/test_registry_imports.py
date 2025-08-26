import pytest

def test_registry_is_exposed_and_aliases():
    from contract_review_app.legal_rules.rules import registry, normalize_clause_type
    assert isinstance(registry, dict)
    # базові ключі
    for k in [
        "governing_law",
        "jurisdiction",
        "indemnity",
        "confidentiality",
        "definitions",
        "termination",
        "force_majeure",
        "oilgas_master_agreement",
    ]:
        assert k in registry
    # аліаси присутні як ключі та нормалізуються
    for alias, target in [
        ("nda", "confidentiality"),
        ("dispute_resolution", "jurisdiction"),
        ("force_majeur", "force_majeure"),
        ("ogma", "oilgas_master_agreement"),
    ]:
        assert alias in registry
        assert normalize_clause_type(alias.upper()) == target

    assert len(registry) >= 15
