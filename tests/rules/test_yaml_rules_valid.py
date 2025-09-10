import pathlib
import yaml
import pytest


ALLOWED_JURISDICTIONS = {
    "England and Wales",
    "Scotland",
    "Northern Ireland",
    "NI",
    "UK",
    "EU",
    "Any",
}


def _yaml_files():
    base1 = pathlib.Path("contract_review_app/legal_rules")
    base2 = pathlib.Path("core/rules")
    return (
        list(base1.rglob("*.yaml"))
        + list(base2.rglob("*.yaml"))
        + list(base2.rglob("*.yml"))
    )


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
        schema = doc.get("schema")
        if schema is None:
            # legacy rule format
            continue
        assert schema == "1.4"

        scope = rule.get("scope", {})
        juris = scope.get("jurisdiction", [])
        assert isinstance(juris, list)
        for j in juris:
            assert j in ALLOWED_JURISDICTIONS

        doc_types = scope.get("doc_types", [])
        assert isinstance(doc_types, list)
        if doc_types == ["Any"] and "universal" not in str(path):
            pytest.fail("doc_types ['Any'] disallowed in specialised packs")

        triggers = rule.get("triggers", {})
        trig_items = triggers.get("any") or triggers.get("all") or []
        assert trig_items, "triggers must be non-empty"

        checks = rule.get("checks", [])
        assert checks, "checks must be non-empty"
