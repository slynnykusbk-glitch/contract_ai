from fastapi.testclient import TestClient

from contract_review_app.api import app as app_module
from contract_review_app.api.models import SCHEMA_VERSION


client = TestClient(app_module.app, headers={"x-schema-version": SCHEMA_VERSION})


def test_summary_cid_not_found():
    resp = client.post("/api/summary", json={"cid": "deadbeef"})
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("error_code") == "cid_not_found"
    assert resp.headers.get("x-cid")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")


def test_summary_bad_json():
    resp = client.post(
        "/api/summary",
        data="{not json}",
        headers={"x-schema-version": SCHEMA_VERSION, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("error_code") == "bad_json"
    assert resp.headers.get("x-cid")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")

