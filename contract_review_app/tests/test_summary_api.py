from fastapi.testclient import TestClient

from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def test_snapshot_positive():
    text = (
        "CONFIDENTIALITY AGREEMENT\n"
        "THIS AGREEMENT is dated 12 March 2024\n"
        "BETWEEN BlackRock Inc and ABC Company Ltd (company number 12345) registered office at 1 High St, London\n"
        "This Agreement shall commence on 12 March 2024 and continue for 12 months unless either party gives 30 days' notice.\n"
        "It shall be governed by the laws of England and Wales and the courts of England and Wales shall have exclusive jurisdiction.\n"
        "The liability of either party shall not exceed £500,000 except for fraud and confidentiality obligations."
    )
    resp = client.post("/api/summary", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    summary = data["summary"]
    assert summary["contract_type"]["type"].lower() in {"nda", "confidentiality"} or any(
        "confidential" in h.lower() for h in summary["contract_type"].get("hints", [])
    )
    assert len(summary["parties"]) >= 2
    assert summary["dates"].get("dated")
    assert summary["term"]["mode"] in {"fixed", "auto_renew"}
    assert "England and Wales" in (summary["law_jurisdiction"].get("law") or "")
    liability = summary["liability"]
    assert liability["has_cap"] is True
    assert liability.get("cap_value") is not None
    carveouts = [c.lower() for c in liability.get("carveouts", [])]
    assert any(c in carveouts for c in ["confidentiality", "fraud"])
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION


def test_snapshot_negative():
    text = "Lorem ipsum dolor sit amet"
    resp = client.post("/api/summary", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    summary = data["summary"]
    assert summary["contract_type"]["type"] == "unknown"
    assert summary["parties"] == []
