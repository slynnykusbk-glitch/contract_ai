from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_analyze_body_ok():
    r = client.post('/api/analyze', json={'schema': '1.4', 'text': 'Ping'}, headers={'x-api-key': 'k', 'x-schema-version': '1.4'})
    assert r.status_code == 200


def test_analyze_broken_body_422_with_details():
    r = client.post('/api/analyze', json={'text': 123}, headers={'x-api-key': 'k', 'x-schema-version': '1.4'})
    assert r.status_code == 422
    detail = r.json().get('detail')
    assert isinstance(detail, list) and any('loc' in d and 'msg' in d for d in detail)
