from fastapi.testclient import TestClient
from contract_review_app.api.app import app


def test_panel_served_with_token_and_no_placeholder():
    client = TestClient(app)
    resp = client.get("/panel/taskpane.html")
    assert resp.status_code == 200
    assert 'data-build="build-' in resp.text
    assert resp.headers.get("Cache-Control") == "no-store, must-revalidate"
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"

    js = client.get("/panel/taskpane.bundle.js")
    assert js.status_code == 200
    assert "__BUILD_TS__" not in js.text
