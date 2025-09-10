import pytest
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


@pytest.mark.skip(reason="legacy summary endpoint replaced")
def test_summary_endpoint(monkeypatch):
    assert True
