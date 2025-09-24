import pathlib
import re
import yaml
import pytest

SAMPLES_DIR = pathlib.Path(__file__).parent / "samples"


def _collect_regex(node):
    patterns = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "regex":
                patterns.append(value)
            else:
                patterns.extend(_collect_regex(value))
    elif isinstance(node, list):
        for item in node:
            patterns.extend(_collect_regex(item))
    return patterns


def load_rule_patterns():
    patterns = {}
    # universal policy packs (inform and performance)
    base = pathlib.Path("contract_review_app/legal_rules/policy_packs/universal")
    for path in base.rglob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        rule = data.get("rule", {})
        rule_id = rule.get("id")
        if not rule_id:
            continue
        regexes = _collect_regex(rule.get("triggers", {}))
        if regexes:
            patterns[rule_id] = regexes
    # core_en_v1 pack
    core_path = pathlib.Path(
        "contract_review_app/legal_rules/policy_packs/core_en_v1.yaml"
    )
    core_data = yaml.safe_load(core_path.read_text())
    for rule in core_data.get("rules", []):
        patterns[rule["id"]] = rule.get("patterns", [])
    return patterns


RULE_PATTERNS = load_rule_patterns()


@pytest.mark.parametrize(
    "sample_file", sorted(SAMPLES_DIR.glob("*.yaml")), ids=lambda p: p.stem
)
def test_rule_samples(sample_file):
    data = yaml.safe_load(sample_file.read_text())
    rule_id = sample_file.stem
    regexes = [re.compile(p, re.MULTILINE) for p in RULE_PATTERNS[rule_id]]
    for text in data.get("positive", []):
        assert any(
            r.search(text) for r in regexes
        ), f"Positive example not matched for {rule_id}: {text}"
    for text in data.get("negative", []):
        assert all(
            not r.search(text) for r in regexes
        ), f"Negative example unexpectedly matched for {rule_id}: {text}"
