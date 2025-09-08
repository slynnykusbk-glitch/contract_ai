import os
import sys
import importlib
import pytest
from fastapi.testclient import TestClient

def _create_client():
    modules = ['contract_review_app.api',
        
        'contract_review_app.api.app',
        'contract_review_app.api.orchestrator',
        'contract_review_app.gpt.service',
        'contract_review_app.gpt.clients.mock_client',
    ]
    for m in modules:
        sys.modules.pop(m, None)
    os.environ.setdefault('LLM_PROVIDER', 'mock')
    from contract_review_app.api import app as app_module
    importlib.reload(app_module)
    client = TestClient(app_module.app)
    return client, modules


@pytest.fixture()
def client():
    client, modules = _create_client()
    try:
        yield client
    finally:
        for m in modules:
            sys.modules.pop(m, None)


def test_qa_recheck_mock_returns_ok(client):
    payload = {'text': 'hello', 'rules': {}}
    resp = client.post('/api/qa-recheck', json=payload)
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'
