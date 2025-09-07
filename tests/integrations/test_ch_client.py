import httpx
import respx

from contract_review_app.integrations.companies_house import client

BASE = client.BASE


def setup_function():
    client._CACHE.clear()  # type: ignore
    client._LAST.clear()  # type: ignore


@respx.mock
def test_search_200():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": []}, headers={"ETag": "e1"}, status_code=200
    )
    data = client.search_companies("ACME")
    assert data["items"] == []
    meta = client.get_last_headers()
    assert meta["cache"] == "miss"


@respx.mock
def test_profile_200():
    respx.get(f"{BASE}/company/123").respond(json={"company_name": "ACME"}, headers={"ETag": "p1"})
    data = client.get_company_profile("123")
    assert data["company_name"] == "ACME"


@respx.mock
def test_304_returns_cache_hit():
    url = f"{BASE}/search/companies"
    respx.get(url).mock(side_effect=[
        httpx.Response(200, json={"items": [1]}, headers={"ETag": "t1"}),
        httpx.Response(304, headers={"ETag": "t1"}),
    ])
    first = client.search_companies("Foo")
    assert first["items"] == [1]
    second = client.search_companies("Foo")
    assert second == first
    assert client.get_last_headers()["cache"] == "hit"


@respx.mock
def test_retry_on_429():
    url = f"{BASE}/company/999"
    respx.get(url).mock(side_effect=[
        httpx.Response(429),
        httpx.Response(200, json={"company_name": "Z"}, headers={"ETag": "e2"}),
    ])
    data = client.get_company_profile("999")
    assert data["company_name"] == "Z"


@respx.mock
def test_timeout_raises():
    url = f"{BASE}/company/888"
    respx.get(url).side_effect = httpx.TimeoutException("boom")
    try:
        client.get_company_profile("888")
    except client.CHTimeout:
        pass
    else:
        assert False, "expected CHTimeout"
