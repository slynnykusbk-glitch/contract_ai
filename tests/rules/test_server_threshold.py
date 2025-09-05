from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)


TEXT = (
    "This Agreement is governed by the laws of England and Wales. "
    "Each party shall keep the other's information confidential. "
    "Company may audit the records at any time."
)


def test_server_threshold_high_filters():
    r = client.post("/api/analyze?risk=high", json={"text": TEXT})
    assert r.status_code == 200
    findings = r.json()["analysis"]["findings"]
    assert findings
    assert all(f["severity"] in ("high", "critical") for f in findings)
