from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
client.headers.update({"x-api-key": "test", "x-schema-version": SCHEMA_VERSION})

def test_title_fields_propagation_minimal():
    body = {"text": "Title shall vest in Company upon manufacture or identification to this Agreement."}
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200
    data = r.json()["analysis"]
    assert data["findings"]
    f0 = data["findings"][0]
    for k in ("rule_id","severity","advice","law_refs","conflict_with","ops","scope","occurrences"):
        assert k in f0
    assert isinstance(f0["law_refs"], list) and f0["law_refs"]
