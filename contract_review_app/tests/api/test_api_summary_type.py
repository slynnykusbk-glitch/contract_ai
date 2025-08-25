from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_api_summary_returns_type():
    text = (
        "NON-DISCLOSURE AGREEMENT\n"
        "Confidential Information may be used only for the Permitted Purpose by the Disclosing Party and the Receiving Party."
    )
    resp = client.post("/api/summary", json={"text": text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["type"] == "NDA"
    assert body["summary"]["type_confidence"] >= 0.6
