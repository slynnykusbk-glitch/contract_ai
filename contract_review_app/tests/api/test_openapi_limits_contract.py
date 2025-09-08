import pytest
from contract_review_app.api.app import app


def test_openapi_contains_limits_and_paging():
    schema = app.openapi()
    paths = schema["paths"]
    analyze_op = paths["/api/analyze"]["post"]
    responses = analyze_op["responses"]
    assert "429" in responses
    assert "504" in responses
    if "/api/corpus/search" not in paths:
        pytest.skip("corpus search not available in this environment")
    search_op = paths["/api/corpus/search"]["post"]
    responses = search_op["responses"]
    assert "429" in responses
    assert "504" in responses
    params = search_op.get("parameters", [])
    assert any(p["name"] == "page" for p in params)
    assert any(p["name"] == "page_size" for p in params)
    assert "Paging" in schema["components"]["schemas"]
    resp_ref = search_op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    resp_name = resp_ref.split("/")[-1]
    resp_schema = schema["components"]["schemas"][resp_name]
    assert "paging" in resp_schema.get("properties", {})
