import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

def test_examples_roundtrip():
    client = TestClient(app)
    live = client.get('/openapi.json').json()
    with open('openapi.json') as f:
        saved = json.load(f)
    assert live == saved
