import sys
import types
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    orig_app = sys.modules.pop("contract_review_app.api.app", None)
    orig_ex = sys.modules.get("contract_review_app.api.explain")

    router = APIRouter(prefix="/api")

    @router.post("/explain")
    def explain(body: dict):
        return {"status": "ok"}

    fake_ex = types.ModuleType("contract_review_app.api.explain")
    fake_ex.router = router
    sys.modules["contract_review_app.api.explain"] = fake_ex

    import contract_review_app.api.app as app_module

    client = TestClient(app_module.app)
    yield client

    if orig_app is not None:
        sys.modules["contract_review_app.api.app"] = orig_app
    else:
        sys.modules.pop("contract_review_app.api.app", None)

    if orig_ex is not None:
        sys.modules["contract_review_app.api.explain"] = orig_ex
    else:
        sys.modules.pop("contract_review_app.api.explain", None)


def test_explain_ok(client):
    payload = {
        "finding": {"span": {"start": 0, "end": 1}, "text": "x", "lang": "latin"}
    }
    r = client.post("/api/explain", json=payload)
    assert r.status_code == 200
