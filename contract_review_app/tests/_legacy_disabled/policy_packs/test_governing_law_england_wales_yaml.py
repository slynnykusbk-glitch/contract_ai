import re
import yaml
from pathlib import Path

RULE_PATH = Path("contract_review_app/legal_rules/policy_packs/governing_law_england_wales.yaml")

def load_rule():
    data = yaml.safe_load(RULE_PATH.read_text())
    assert isinstance(data, list) and data, "Rule file should contain a list with one rule"
    return data[0]

def test_positive_examples_pass_checks():
    rule = load_rule()
    must_include = [re.compile(pat, re.I) for pat in rule["checks"]["must_include"]]
    must_exclude = [re.compile(pat, re.I) for pat in rule["checks"]["must_exclude"]]
    for text in rule["examples"]["positive"]:
        assert any(re.search(trig, text) for trig in rule["triggers"]["any"])
        for rx in must_include:
            assert rx.search(text)
        for rx in must_exclude:
            assert not rx.search(text)

def test_negative_examples_fail_includes():
    rule = load_rule()
    must_include = [re.compile(pat, re.I) for pat in rule["checks"]["must_include"]]
    for text in rule["examples"]["negative"]:
        assert not all(rx.search(text) for rx in must_include)
