from contract_review_app.legal_rules import loader


def test_loader_skips_non_yaml(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "ok.yaml").write_text("rule:\n  id: ok\n", encoding="utf-8")
    (rules_dir / "legacy.py").write_text("# legacy", encoding="utf-8")

    rules = loader.load_rules(base_dir=rules_dir)
    ids = {r.get("rule_id") or r.get("id") for r in rules}
    assert "ok" in ids
    assert ids == {"ok"}
