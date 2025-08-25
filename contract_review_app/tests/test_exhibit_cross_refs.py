from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

TEXT_POSITIVE = (
    "INFORMATION SYSTEMS ACCESS\n"
    "Contractor will access Company systems. See EXHIBIT L – INFORMATION SYSTEMS ACCESS AND DATA SECURITY.\n"
    "DATA PROTECTION\n"
    "The Parties shall comply with UK GDPR. See EXHIBIT M – DATA PROTECTION."
)

TEXT_MISSING_M = (
    "INFORMATION SYSTEMS ACCESS\n"
    "Contractor will access Company systems. See EXHIBIT L – INFORMATION SYSTEMS ACCESS AND DATA SECURITY.\n"
    "DATA PROTECTION\n"
    "The Parties shall comply with UK GDPR."
)

def test_analyze_flags_missing_exhibit_m():
    r = client.post("/api/analyze", json={"text": TEXT_MISSING_M})
    assert r.status_code == 200
    doc = r.json()["document"]
    analyses = doc.get("analyses", [])
    ex_m = next(a for a in analyses if a["clause_type"] == "exhibits_M_present")
    assert ex_m["status"] == "FAIL"
    assert any(f["code"] == "EXHIBIT-M-MISSING" for f in ex_m.get("findings", []))
    dp = next(a for a in analyses if a["clause_type"] == "data_protection")
    assert dp["status"] == "FAIL"
    assert any("Exhibit M" in f["message"] for f in dp.get("findings", []))

    r2 = client.post("/api/suggest_edits", json={"text": TEXT_MISSING_M, "clause_type": "data_protection"})
    assert r2.status_code == 200
    suggestions = r2.json().get("suggestions", [])
    assert any("Exhibit M" in s.get("message", "") for s in suggestions)

def test_analyze_passes_when_exhibits_present():
    r = client.post("/api/analyze", json={"text": TEXT_POSITIVE})
    assert r.status_code == 200
    analyses = r.json()["document"].get("analyses", [])
    ex_l = next(a for a in analyses if a["clause_type"] == "exhibits_L_present")
    ex_m = next(a for a in analyses if a["clause_type"] == "exhibits_M_present")
    assert ex_l["status"] == "OK"
    assert ex_m["status"] == "OK"
