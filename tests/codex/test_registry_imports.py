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
    # аліаси працюють
    assert normalize_clause_type("NDA") == "confidentiality"
