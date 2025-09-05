from __future__ import annotations

import re
from pathlib import Path

import yaml

from contract_review_app.legal_rules import loader

BASE = Path(loader.__file__).resolve().parent / "policy_packs" / "universal"


def _sample_from_pattern(pattern: str) -> str:
    candidates = [pattern]
    parts = pattern.split("|")
    if parts:
        first = re.sub(r"\(\?i\)", "", parts[0])
        first = re.sub(r"\\s+", " ", first)
        first = re.sub(r"[^a-zA-Z0-9 ]", "", first).strip()
        if first:
            candidates.append(first)
        last = re.sub(r"\(\?i\)", "", parts[-1])
        last = re.sub(r"\\s+", " ", last)
        last = re.sub(r"[^a-zA-Z0-9 ]", "", last).strip()
        if last:
            candidates.append(last)
    for text in candidates:
        if re.search(pattern, text, re.I):
            return text
    return "sample"


def test_inventory_loaded_packs():
    loader.load_rule_packs()
    packs = loader.loaded_packs()
    universal_files = {p.stem for p in BASE.rglob("*.yaml")}
    loaded_names = {Path(p["file"]).stem for p in packs if "universal" in p["file"]}
    assert universal_files <= loaded_names
    assert loader.rules_count() >= len(universal_files)


# dynamically ensure at least one trigger fires for each universal rule
specs = []
for path in BASE.rglob("*.yaml"):
    data = yaml.safe_load(path.read_text())
    spec = data.get("rule", {})
    trig = spec.get("triggers", {}).get("any", [])
    if not trig:
        continue
    pat = trig[0]["regex"] if isinstance(trig[0], dict) else trig[0]
    specs.append((spec.get("id"), pat))


import pytest  # noqa: E402


OVERRIDES = {
    "universal.inform.discrepancy_notice_timebar": "discrepanc notice",
    "universal.inform.employer_info_nonreliance": "information provided by Employer",
}

@pytest.mark.parametrize("rule_id,pattern", specs)
def test_rule_triggers(rule_id: str, pattern: str):
    loader.load_rule_packs()
    text = OVERRIDES.get(rule_id, _sample_from_pattern(pattern))
    findings = loader.match_text(text)
    assert any(f["rule_id"] == rule_id for f in findings)
