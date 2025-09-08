from fastapi.testclient import TestClient
from contract_review_app.api.app import app


def test_one_of_rule_ok():
    with TestClient(app) as c:
        ok1 = c.post(
            "/api/citation/resolve",
            json={"citations": [{"instrument": "Act", "section": "1"}]},
        )
        assert ok1.status_code == 200
        ok2 = c.post(
            "/api/citation/resolve", json={"findings": [{"code": "X", "message": "m"}]}
        )
        assert ok2.status_code == 200


def test_one_of_rule_fails_clean():
    with TestClient(app) as c:
        r1 = c.post("/api/citation/resolve", json={"findings": [], "citations": []})
        r2 = c.post("/api/citation/resolve", json={})
        for r in (r1, r2):
            assert r.status_code == 400
            assert "Exactly one of findings or citations is required" in r.text
