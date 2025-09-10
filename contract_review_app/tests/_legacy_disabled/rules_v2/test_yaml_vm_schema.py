import yaml

from contract_review_app.rules_v2 import models, vm, yaml_schema


def build_yaml(tmp_path):
    content = {
        "id": "rule1",
        "pack": "pack1",
        "severity": "High",
        "category": "cat",
        "title": {"en": "Title EN"},
        "message": {"en": "Message EN"},
        "explain": {"en": "Explain EN"},
        "suggestion": {"en": "Suggestion EN"},
        "version": "2.0.0",
        "engine_version": models.ENGINE_VERSION,
        "checks": [
            {
                "when": "context.text contains 'NDA'",
                "all_of": ["context.meta.type == 'confidentiality'"],
                "produce": {"evidence": ["found A"], "flags": ["dsl"]},
            }
        ],
    }
    path = tmp_path / "rule.yaml"
    path.write_text(yaml.safe_dump(content))
    return path


def test_schema_and_vm(tmp_path):
    path = build_yaml(tmp_path)
    data = yaml.safe_load(path.read_text())
    rule = yaml_schema.RuleYaml.model_validate(data)
    machine = vm.RuleVM(rule)

    context = {"text": "NDA draft", "meta": {"type": "confidentiality"}}
    findings = machine.evaluate(context)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "High"
    assert f.title["en"] == "Title EN"
    assert f.engine_version == models.ENGINE_VERSION

    context = {"text": "draft", "meta": {"type": "confidentiality"}}
    assert machine.evaluate(context) == []
