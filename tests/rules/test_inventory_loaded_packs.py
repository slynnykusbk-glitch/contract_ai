from contract_review_app.legal_rules import loader


def test_inventory_loaded_packs():
    loader.load_rule_packs()
    assert loader.rules_count() >= 150
    packs = loader.loaded_packs()
    assert all(not p["path"].endswith(".py") for p in packs)
    dups = loader.meta.get("debug", {}).get("duplicates")
    assert isinstance(dups, dict)
