from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def _check_etag_flow(path, payload):
    r1 = client.post(path, json=payload)
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag
    assert r1.headers.get("x-cache") == "miss"

    r2 = client.post(path, json=payload, headers={"If-None-Match": etag})
    assert r2.status_code == 304

    r3 = client.post(path, json=payload)
    assert r3.status_code == 200
    assert r3.headers.get("x-cache") == "hit"
    assert r3.headers.get("ETag") == etag


def test_analyze_cache_headers():
    _check_etag_flow("/api/analyze", {"text": "hello"})


def test_gpt_draft_cache_headers():
    r = client.post("/api/analyze", json={"text": "hello"})
    cid = r.headers.get("x-cid")
    _check_etag_flow("/api/gpt-draft", {"cid": cid, "clause": "hello", "mode": "friendly"})
