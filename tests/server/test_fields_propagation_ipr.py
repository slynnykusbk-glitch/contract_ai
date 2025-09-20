from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
client.headers.update({"x-api-key": "test", "x-schema-version": SCHEMA_VERSION})

def test_ipr_fields_propagation_minimal():
    body = {"text": "Title to the Agreement Documentation shall vest in Company."}
    resp = client.post("/api/analyze", json=body)
    assert resp.status_code == 200
    data = resp.json()
    findings = data["analysis"]["findings"]
    assert findings
    f0 = findings[0]
    for key in ("rule_id","severity","advice","law_refs","scope","occurrences","conflict_with","ops"):
        assert key in f0
    assert isinstance(f0["law_refs"], list)
    assert isinstance(f0["conflict_with"], list)
    assert isinstance(f0["ops"], list)
    assert isinstance(f0["scope"], dict)
