from pathlib import Path

import yaml

from contract_review_app.rules_v2 import loader, models, types


def create_rules(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()

    # python-only rule
    (pack / "py_rule.py").write_text(
        """
from contract_review_app.rules_v2 import models

def apply(context):
    return [models.FindingV2(id='py', pack='pack', severity='Low', category='c', title={'en':'t'}, version='2.0.0')]
""",
    )

    # hybrid rule: both .py and .yaml
    (pack / "hybrid_rule.py").write_text(
        """
from contract_review_app.rules_v2 import models

def apply(context):
    return [models.FindingV2(id='hy', pack='pack', severity='Low', category='c', title={'en':'t'}, version='2.0.0')]
""",
    )
    (pack / "hybrid_rule.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "hy",
                "pack": "pack",
                "severity": "Low",
                "category": "c",
                "title": {"en": "t"},
                "version": "2.0.0",
                "engine_version": models.ENGINE_VERSION,
                "checks": [{"when": True}],
            }
        )
    )

    # yaml-only rule
    (pack / "yaml_rule.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "yaml",
                "pack": "pack",
                "severity": "Low",
                "category": "c",
                "title": {"en": "t"},
                "version": "2.0.0",
                "engine_version": models.ENGINE_VERSION,
                "checks": [{"when": False}],
            }
        )
    )

    return pack


def test_discover_and_execute(tmp_path):
    create_rules(tmp_path)
    rules = loader.discover(tmp_path)
    assert {r.id: r.format for r in rules} == {
        "hybrid_rule": types.RuleFormat.HYBRID,
        "py_rule": types.RuleFormat.PYTHON,
        "yaml_rule": types.RuleFormat.YAML,
    }

    for rule in rules:
        loader.execute(rule, {"text": "NDA", "meta": {"type": "confidentiality"}})
