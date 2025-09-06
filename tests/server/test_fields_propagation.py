from pathlib import Path
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

TEXT = Path('tests/fixtures/quality_clause13.txt').read_text()

def test_fields_propagation():
    r = client.post('/api/analyze', json={'text': TEXT})
    assert r.status_code == 200
    findings = r.json()['analysis']['findings']
    assert len(findings) >= 3
    for f in findings:
        assert f.get('advice')
        assert isinstance(f.get('law_refs'), list) and f['law_refs']
        assert isinstance(f.get('conflict_with'), list)
        assert isinstance(f.get('ops'), list)
        assert isinstance(f.get('scope'), dict)
        assert isinstance(f.get('occurrences'), int) and f['occurrences'] >= 1
