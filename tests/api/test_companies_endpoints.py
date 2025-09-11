import os
import httpx
import respx
from fastapi.testclient import TestClient

os.environ["FEATURE_INTEGRATIONS"] = "1"
os.environ["FEATURE_COMPANIES_HOUSE"] = "1"
os.environ["CH_API_KEY"] = "x"

import importlib
import contract_review_app.config as cfg
import contract_review_app.api.integrations as integrations
import contract_review_app.api.app as app_module
from contract_review_app.integrations.companies_house import client as ch_client

importlib.reload(cfg)
importlib.reload(ch_client)
importlib.reload(integrations)
importlib.reload(app_module)

client = TestClient(app_module.app)
BASE = ch_client.BASE
ch_client.KEY = "x"
os.environ["FEATURE_COMPANIES_HOUSE"] = "1"
integrations.CH_API_KEY = "x"
integrations.FEATURE_COMPANIES_HOUSE = "1"


@respx.mock
def test_search_endpoint(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    respx.get(f"{BASE}/search/companies").respond(
        json={
            "items": [
                {
                    "company_number": "42",
                    "title": "ACME",
                    "address_snippet": "1 Road, City",
                    "company_status": "active",
                }
            ]
        },
        headers={"ETag": "s1"},
    )
    expected = [
        {
            "company_number": "42",
            "company_name": "ACME",
            "address_snippet": "1 Road, City",
            "status": "active",
        }
    ]
    r = client.post("/api/companies/search", json={"query": "ACME"})
    assert r.status_code == 200
    assert r.json() == expected
    assert r.headers.get("ETag") == "s1"
    assert r.headers.get("x-cache") == "miss"
    r2 = client.get("/api/companies/search", params={"q": "ACME"})
    assert r2.status_code == 200
    assert r2.json() == expected


@respx.mock
def test_profile_endpoint(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    profile = {
        "company_number": "42",
        "company_name": "ACME LIMITED",
        "company_status": "active",
        "type": "ltd",
        "jurisdiction": "england-wales",
        "date_of_creation": "2020-01-01",
        "registered_office_address": {
            "address_line_1": "10 Downing Street",
            "address_line_2": "Suite 42",
            "postal_code": "SW1A 2AA",
            "locality": "London",
            "country": "United Kingdom",
        },
        "sic_codes": ["12345"],
        "accounts": {
            "last_accounts": {"made_up_to": "2023-12-31"},
            "next_accounts": {"due_on": "2024-12-31"},
        },
        "confirmation_statement": {
            "last_made_up_to": "2023-06-01",
            "next_due": "2024-06-01",
        },
    }
    respx.get(f"{BASE}/company/42").respond(json=profile, headers={"ETag": "p1"})
    respx.get(f"{BASE}/company/42/officers?items_per_page=1").respond(
        json={"total_results": 5}
    )
    respx.get(
        f"{BASE}/company/42/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 1})
    r = client.get("/api/companies/42")
    assert r.status_code == 200
    assert r.headers.get("ETag") == "p1"
    assert r.json() == {
        "company_number": "42",
        "company_name": "ACME LIMITED",
        "status": "active",
        "company_type": "ltd",
        "jurisdiction": "england-wales",
        "incorporated_on": "2020-01-01",
        "registered_office": {
            "address_line": "10 Downing Street, Suite 42",
            "postcode": "SW1A 2AA",
            "locality": "London",
            "country": "United Kingdom",
        },
        "sic_codes": ["12345"],
        "accounts": {
            "last_made_up_to": "2023-12-31",
            "next_due": "2024-12-31",
        },
        "confirmation_statement": {
            "last_made_up_to": "2023-06-01",
            "next_due": "2024-06-01",
        },
        "officers_count": 5,
        "psc_count": 1,
    }


def test_disabled(monkeypatch):
    monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", "0")
    import importlib
    import contract_review_app.config as cfg
    import contract_review_app.api.integrations as integrations
    import contract_review_app.integrations.companies_house.client as ch_client
    import contract_review_app.api.app as app_module

    importlib.reload(cfg)
    importlib.reload(ch_client)
    importlib.reload(integrations)
    importlib.reload(app_module)
    local_client = TestClient(app_module.app)
    r = local_client.post("/api/companies/search", json={"query": "A"})
    assert r.status_code == 403
    assert r.json() == {"status": "disabled"}
    monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", "1")
    importlib.reload(cfg)
    importlib.reload(ch_client)
    importlib.reload(integrations)
    importlib.reload(app_module)


@respx.mock
def test_etag_round_trip(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    url = f"{BASE}/company/77"
    respx.get(url).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"company_number": "77", "company_name": "AC"},
                headers={"ETag": "e3"},
            ),
            httpx.Response(304, headers={"ETag": "e3"}),
        ]
    )
    off_route = respx.get(f"{BASE}/company/77/officers?items_per_page=1").respond(
        json={"total_results": 1}
    )
    psc_route = respx.get(
        f"{BASE}/company/77/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 0})
    r1 = client.get("/api/companies/77")
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert r1.headers.get("x-cache") == "miss"
    r2 = client.get("/api/companies/77", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers.get("x-cache") == "hit"
    assert off_route.call_count == 1
    assert psc_route.call_count == 1


@respx.mock
def test_profile_not_found(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    respx.get(f"{BASE}/company/404").respond(status_code=404)
    r = client.get("/api/companies/404")
    assert r.status_code == 404
    assert r.json() == {"error": "company_not_found"}


@respx.mock
def test_profile_rate_limited(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    url = f"{BASE}/company/55"
    respx.get(url).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "11"}),
            httpx.Response(429, headers={"Retry-After": "11"}),
            httpx.Response(429, headers={"Retry-After": "11"}),
        ]
    )
    r = client.get("/api/companies/55")
    assert r.status_code == 429
    assert r.json() == {"error": "rate_limited"}
    assert r.headers.get("Retry-After") == "11"


@respx.mock
def test_profile_5xx(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    url = f"{BASE}/company/56"
    respx.get(url).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ]
    )
    r = client.get("/api/companies/56")
    assert r.status_code == 502
    assert r.json() == {"error": "upstream_error"}
