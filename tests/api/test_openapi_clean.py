from fastapi.testclient import TestClient
from contract_review_app.api.app import app


def test_no_duplicate_paths_or_operation_ids():
    spec = TestClient(app).get("/openapi.json").json()
    paths = set(spec["paths"].keys())
    assert "/api/gpt/draft" not in paths
    assert "/api/gpt_draft" not in paths
    assert "/gpt-draft" not in paths
    assert "/api/citations/resolve" not in paths
    ids = [op.get("operationId") for p in spec["paths"].values() for op in p.values() if "operationId" in op]
    assert len(ids) == len(set(ids))
