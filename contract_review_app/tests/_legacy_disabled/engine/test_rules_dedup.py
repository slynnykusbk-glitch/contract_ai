import pathlib

import pytest

from contract_review_app.legal_rules import loader
from tools import validate_rules

YAML_A = "rule_id: duplicate_x\nTitle: From policy_packs\n"
YAML_B = "rule_id: duplicate_x\nTitle: From core\n"


def write(p: pathlib.Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_loader_picks_higher_priority(tmp_path, monkeypatch):
    root_pp = tmp_path / "contract_review_app/legal_rules/policy_packs"
    root_core = tmp_path / "core/rules"

    write(root_pp / "pack/a.yaml", YAML_A)
    write(root_core / "some/b.yaml", YAML_B)

    monkeypatch.setattr(loader, "RULE_ROOTS", [str(root_pp), str(root_core)])

    rules = loader.load_rules()
    ids = {r["rule_id"] for r in rules}
    assert "duplicate_x" in ids
    chosen = next(r for r in rules if r["rule_id"] == "duplicate_x")
    assert chosen.get("Title") == "From policy_packs"


def test_validate_rules_detects_conflicts(tmp_path, capsys):
    root_pp = tmp_path / "contract_review_app/legal_rules/policy_packs"
    root_core = tmp_path / "core/rules"
    write(root_pp / "pack/a.yaml", "rule_id: conflict_1\nTitle: V1\n")
    write(root_core / "pack/a.yaml", "rule_id: conflict_1\nTitle: V2\n")

    with pytest.raises(SystemExit) as exc:
        validate_rules.validate([root_pp, root_core])
    assert exc.value.code == 2
    out = capsys.readouterr().out.lower()
    assert "conflicting" in out or "conflict" in out
