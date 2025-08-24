from contract_review_app.legal_rules.rules import registry


def test_discover_rules():
    # All expected rule keys (canonical names and important aliases) should be present in the registry
    expected_rules = {
        "governing_law",
        "jurisdiction",
        "dispute_resolution",
        "termination",
        "force_majeure",
        "indemnity",
        "limitation_of_liability",
        "confidentiality",
        "non_disclosure",
        "intellectual_property",
        "license_grant",
        "moral_rights",
        "payment_terms",
        "invoicing",
        "taxes",
        "warranties",
        "representations",
        "assignment",
        "subcontracting",
        "data_protection_gdpr",
        "audit_rights",
        "non_solicitation",
        "non_compete",
        "entire_agreement",
        "notices",
    }
    for key in expected_rules:
        assert key in registry.RULES, f"Expected rule '{key}' to be registered in RULES"
    # Alias mapping: e.g., 'non_disclosure' should map to 'confidentiality' if configured in ALIASES
    if "confidentiality" in registry.RULES:
        assert "non_disclosure" in registry.RULES
        assert registry.RULES["non_disclosure"] == registry.RULES["confidentiality"]
    # All registered rule entries should be callable functions
    for rule_func in registry.RULES.values():
        assert callable(
            rule_func
        ), "Each entry in RULES should be a callable analyze function"
