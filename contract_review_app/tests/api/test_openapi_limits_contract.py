from contract_review_app.api.app import app


def test_openapi_contains_limits_and_paging():
    schema = app.openapi()
    paths = schema['paths']
    for p in ('/api/analyze', '/api/corpus/search'):
        op = paths[p]['post']
        responses = op['responses']
        assert '429' in responses
        assert '504' in responses
    search_op = paths['/api/corpus/search']['post']
    params = search_op.get('parameters', [])
    assert any(p['name'] == 'page' for p in params)
    assert any(p['name'] == 'page_size' for p in params)
    assert 'Paging' in schema['components']['schemas']
    resp_ref = search_op['responses']['200']['content']['application/json']['schema']['$ref']
    resp_name = resp_ref.split('/')[-1]
    resp_schema = schema['components']['schemas'][resp_name]
    assert 'paging' in resp_schema.get('properties', {})
