from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_analyze_payload_wrapper_ok():
    r = client.post('/api/analyze', json={'payload': {'schema': '1.4', 'mode': 'live', 'text': 'Ping'}}, headers={'x-api-key': 'k', 'x-schema-version': '1.4'})
    assert r.status_code == 200


def test_analyze_flat_body_rejected():
    r = client.post('/api/analyze', json={'schema': '1.4', 'text': 'Ping'}, headers={'x-api-key': 'k', 'x-schema-version': '1.4'})
    assert r.status_code == 422
