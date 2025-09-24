import os
import json
import yaml
from src.risk_indemnities_analyzer import analyze

# Embedded fragment with required phrases
FALLBACK = """
Consequential Loss means any or all of the following: loss or deferment of revenue, profit or anticipated profit;
loss of use, loss and or deferral of production; loss of business opportunity or goodwill; and any Claim arising therefrom.
Consequential Loss does not include liquidated damages ... defence costs ... third party judgments ... damages for breach of confidentiality.
Indemnify means defend, indemnify, release, and hold harmless.
Company shall not be deemed to have accepted any Goods until Company has had a reasonable time to inspect them following delivery.
"""


def load_text():
    path = os.environ.get("CONTRACT_DOCX_PATH")
    if path and os.path.exists(path):
        return None, path
    return FALLBACK, None


def test_integration_master_agreement_smoke():
    text, path = load_text()
    out = analyze(text=text, path=path)
    r = out["risk_indemnities"]

    assert r["indemnify_defend_hold_harmless"]["present"] is True
    assert r["consequential_loss_defined"]["present"] is True
    assert r["consequential_loss_carveouts_present"]["present"] is True
    assert r["goods_risk_until_acceptance"]["present"] is True

    y = yaml.dump(out, sort_keys=False)
    assert 'version: "1.0.0"' in y
