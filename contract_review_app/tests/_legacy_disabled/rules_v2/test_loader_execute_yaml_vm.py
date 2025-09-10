from datetime import datetime
from pathlib import Path

import yaml

from contract_review_app.rules_v2 import loader, models


def create_pack(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()
    content = {
        "id": "r1",
        "pack": "pack",
        "severity": "Medium",
        "category": "cat",
        "title": {"en": "Title"},
        "version": "2.0.0",
        "engine_version": models.ENGINE_VERSION,
        "checks": [
            {
                "when": "context.text contains 'NDA'",
                "any_of": ["context.meta.type == 'confidentiality'"],
                "produce": {"evidence": ["hit"], "citation": ["http://example.com"]},
            }
        ],
    }
    (pack / "rule.yaml").write_text(yaml.safe_dump(content))
    return pack


def test_loader_execute_yaml(tmp_path):
    create_pack(tmp_path)
    discovered = loader.discover(tmp_path)
    assert discovered and discovered[0].format.value == "yaml"
    findings = loader.execute(
        discovered[0], {"text": "NDA draft", "meta": {"type": "confidentiality"}}
    )
    assert findings
    f = findings[0]
    assert isinstance(f.created_at, datetime)
    assert f.engine_version == models.ENGINE_VERSION
