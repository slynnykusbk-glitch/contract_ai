from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
client.headers.update({"x-api-key": "test", "x-schema-version": SCHEMA_VERSION})

TEXT = "Contractor shall produce an inspection and test plan (ITP). The ITP will list inspections only."


def test_fields_propagation_quality():
    r = client.post('/api/analyze', json={'text': TEXT})
    assert r.status_code == 200
    findings = r.json()['analysis']['findings']
    assert findings
    for f in findings:
        assert f.get('advice')
        assert isinstance(f.get('law_refs'), list) and f['law_refs']
        assert isinstance(f.get('ops'), list)
        assert isinstance(f.get('scope'), dict)
        assert isinstance(f.get('occurrences'), int) and f['occurrences'] >= 1
