import os
from fastapi.testclient import TestClient

os.environ.setdefault('FEATURE_COMPANIES_HOUSE', '1')
os.environ.setdefault('CH_API_KEY', 'x')

from contract_review_app.api.app import app


def test_openapi_contains_paths_and_models():
    spec = TestClient(app).get('/openapi.json').json()
    paths = spec['paths']
    assert '/api/summary' in paths
    assert '/api/gpt-draft' in paths
    assert '/api/draft' in paths
    assert '/api/supports' in paths
    assert '/api/companies/search' in paths
    schemas = spec['components']['schemas']
    for name in ('SummaryIn', 'DraftRequest', '_CompanySearchIn'):
        assert name in schemas
