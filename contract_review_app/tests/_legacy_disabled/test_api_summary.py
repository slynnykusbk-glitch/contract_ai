import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from contract_review_app.api.app import app
from contract_review_app.core.schemas import SCHEMA_VERSION


@pytest.fixture
def client():
    return TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})


def test_summary_endpoint_nda(client):
    payload = {
        "text": (
            "CONFIDENTIALITY AGREEMENT BETWEEN ABC Company (Disclosing Party) and XYZ Ltd (Receiving Party). "
            "Effective Date 1 January 2024. This Agreement shall commence on the Effective Date and continue for a period of 2 years. "
            "This Agreement is governed by the laws of England and Wales and parties submit to the exclusive jurisdiction of the courts of England. "
            "The liability of either party shall not exceed £100,000. Confidential Information shall not include information which is in the public domain. "
            "The Seller warrants that goods are fit. The following is a condition of this Agreement."
        )
    }
    r_analyze = client.post("/api/analyze", json=payload)
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    resp = client.post("/api/summary", json={"cid": cid})
    assert resp.status_code == 200
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION
    data = resp.json()
    summary = data["summary"]
    assert summary["type"] == "NDA"
    assert summary["type_confidence"] > 0.5
    assert summary["parties"][0]["role"] == "Disclosing Party"
    assert summary["dates"]["effective"] == "1 January 2024"
    assert summary["term"]["mode"] in ["fixed", "auto_renew"]
    assert summary["governing_law"]
    assert summary["jurisdiction"]
    assert summary["liability"]["has_cap"] is True
    assert abs(summary["liability"]["cap_value"] - 100000) < 1e-6
    assert summary["liability"]["cap_currency"] == "GBP"
    cw = summary["conditions_vs_warranties"]
    assert cw["has_conditions"] or cw["has_warranties"]
    carve = summary["carveouts"]
    assert carve["has_carveouts"]
    assert len(carve["carveouts"]) >= 1


def test_summary_endpoint_license(client):
    text = "LICENSE AGREEMENT between Foo Corp (Licensor) and Bar Inc (Licensee)."
    r_analyze = client.post("/api/analyze", json={"text": text})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    resp = client.post("/api/summary", json={"cid": cid})
    assert resp.status_code == 200
    data = resp.json()["summary"]
    assert data["type"] == "License"
    roles = [p["role"] for p in data["parties"]]
    assert "Licensor" in roles and "Licensee" in roles
