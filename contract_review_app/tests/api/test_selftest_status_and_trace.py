from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_health_ok_lowercase():
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert r.headers.get("x-cid")


def test_analyze_has_body_and_cid():
    r = client.post("/api/analyze", json={"text": "x", "mode": "live"})
    assert r.status_code == 200
    assert r.content and r.headers.get("content-length") != "0"
    assert r.headers.get("x-cid")


def test_trace_list_and_get():
    client.get("/health")
    lst = client.get("/api/trace").json()["cids"]
    assert lst
    one = client.get(f"/api/trace/{lst[-1]}")
    assert one.status_code == 200
    assert "body" in one.json()
