import pathlib
import yaml
import pytest


def _yaml_files():
    base1 = pathlib.Path("contract_review_app/legal_rules")
    base2 = pathlib.Path("core/rules")
    return list(base1.rglob("*.yaml")) + list(base2.rglob("*.yaml")) + list(base2.rglob("*.yml"))


@pytest.mark.parametrize("path", _yaml_files())
def test_yaml_rule_valid(path):
    docs = list(yaml.safe_load_all(path.read_text()))
    assert docs, f"{path} empty"
    for doc in docs:
        rule = doc.get("rule") if isinstance(doc, dict) else None
        if not isinstance(rule, dict):
            continue
        if not isinstance(rule.get("id"), str) or not rule["id"]:
            continue
        scope = rule.get("scope", {})
        juris = scope.get("jurisdiction", [])
        assert isinstance(juris, list)
        doc_types = scope.get("doc_types", [])
        assert isinstance(doc_types, list)
        if "independent_contractor" in str(path):
            assert doc_types != ["Any"]
