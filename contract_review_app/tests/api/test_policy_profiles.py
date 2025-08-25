from fastapi.testclient import TestClient

import importlib
from contract_review_app.api import app as api_app

importlib.reload(api_app)  # ensure latest pipeline
api_app.run_suggest_edits = None  # ensure pipeline path
client = TestClient(api_app.app)


def _payload():
    return {"text": "Each party shall keep information confidential.", "clause_type": "confidentiality"}


def test_suggest_edits_profile_variants():
    base = _payload()
    r_friendly = client.post("/api/suggest_edits", json={**base, "policy_profile": "friendly"})
    r_firm = client.post("/api/suggest_edits", json={**base, "policy_profile": "firm"})
    r_hard = client.post("/api/suggest_edits", json={**base, "policy_profile": "hard"})

    friendly_text = r_friendly.json()["suggestions"][0]["proposed_text"]
    firm_text = r_firm.json()["suggestions"][0]["proposed_text"]
    hard_text = r_hard.json()["suggestions"][0]["proposed_text"]

    assert "3" in friendly_text
    assert "5" in firm_text
    assert "indefinitely" in hard_text.lower()

    r_default = client.post("/api/suggest_edits", json=base)
    assert r_default.json()["suggestions"][0]["proposed_text"] == friendly_text
