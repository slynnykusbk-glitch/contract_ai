from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})


def test_api_summary_returns_type():
    text = (
        "NON-DISCLOSURE AGREEMENT\n"
        "Confidential Information may be used only for the Permitted Purpose by the Disclosing Party and the Receiving Party."
    )
    r_analyze = client.post("/api/analyze", json={"text": text})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    resp = client.post("/api/summary", json={"cid": cid})
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["type"] == "NDA"
    assert body["summary"]["type_confidence"] >= 0.6
