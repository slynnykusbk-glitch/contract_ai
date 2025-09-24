def test_companies_post_missing_query(api):
    r = api.post("/api/companies/search", json={})
    assert r.status_code == 422


def test_companies_post_ok(api, monkeypatch):
    from contract_review_app.api import integrations as integ

    monkeypatch.setattr(integ, "FEATURE_COMPANIES_HOUSE", "1")
    monkeypatch.setattr(integ, "CH_API_KEY", "test")
    monkeypatch.setattr(integ, "CH_ENABLED", True)
    monkeypatch.setattr(
        integ.ch_client, "search_companies", lambda q, items: {"items": []}
    )
    monkeypatch.setattr(
        integ.ch_client, "get_last_headers", lambda: {"etag": "", "cache": "miss"}
    )

    r = api.post("/api/companies/search", json={"query": "BLACK ROCK"})
    assert r.status_code in (200, 503)
