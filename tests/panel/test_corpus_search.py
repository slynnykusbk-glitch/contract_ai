import sys
import types
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    orig_app = sys.modules.pop("contract_review_app.api.app", None)
    orig_cs = sys.modules.get("contract_review_app.api.corpus_search")

    router = APIRouter(prefix="/api/corpus")

    @router.post("/search")
    def search(body: dict):
        return {"hits": []}

    fake_cs = types.ModuleType("contract_review_app.api.corpus_search")
    fake_cs.router = router
    sys.modules["contract_review_app.api.corpus_search"] = fake_cs

    import contract_review_app.api.app as app_module

    client = TestClient(app_module.app)
    yield client

    if orig_app is not None:
        sys.modules["contract_review_app.api.app"] = orig_app
    else:
        sys.modules.pop("contract_review_app.api.app", None)

    if orig_cs is not None:
        sys.modules["contract_review_app.api.corpus_search"] = orig_cs
    else:
        sys.modules.pop("contract_review_app.api.corpus_search", None)


def test_corpus_search_ok(client):
    r = client.post("/api/corpus/search", json={"q": "x"})
    assert r.status_code == 200
