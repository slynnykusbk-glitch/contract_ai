import os
import importlib
from fastapi.testclient import TestClient


def _build_client() -> TestClient:
    os.environ["CONTRACTAI_LLM_API"] = "1"
    import contract_review_app.api.app as app_module

    importlib.reload(app_module)
    client = TestClient(app_module.app)
    os.environ.pop("CONTRACTAI_LLM_API", None)
    return client


def test_problem_detail_component():
    client = _build_client()
    schema = client.get("/openapi.json").json()
    assert "ProblemDetail" in schema["components"]["schemas"]


def test_problem_detail_responses():
    client = _build_client()
    schema = client.get("/openapi.json").json()
    for path in ["/api/analyze", "/api/gpt-draft", "/api/citation/resolve"]:
        post = schema["paths"][path]["post"]
        ref_500 = post["responses"]["500"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        assert ref_500 == "#/components/schemas/ProblemDetail"
        ref_422 = post["responses"]["422"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        if path == "/api/analyze":
            assert ref_422.endswith("HTTPValidationError")
        else:
            assert ref_422 == "#/components/schemas/ProblemDetail"
