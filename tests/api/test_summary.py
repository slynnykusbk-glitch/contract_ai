def test_summary_requires_one_of(api):
    r = api.post("/api/summary", json={"text": "oops"})
    assert r.status_code == 422


def test_summary_happy_path(api, sample_cid):
    r = api.post("/api/summary", json={"cid": sample_cid})
    assert r.status_code == 200
    assert r.json()["summary"]["type"] in ("NDA", "unknown")
