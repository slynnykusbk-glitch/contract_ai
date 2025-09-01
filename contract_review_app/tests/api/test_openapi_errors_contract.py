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
    for path in ["/api/analyze", "/api/gpt-draft", "/api/citations/resolve"]:
        post = schema["paths"][path]["post"]
        for code in ("422", "500"):
            ref = post["responses"][code]["content"]["application/json"]["schema"]["$ref"]
            assert ref == "#/components/schemas/ProblemDetail"
