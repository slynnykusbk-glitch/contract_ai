import os
import respx

from contract_review_app.integrations.companies_house import client as ch_client

BASE = ch_client.BASE


def setup_function():
    ch_client._CACHE.clear()  # type: ignore
    ch_client._LAST.clear()  # type: ignore
    os.environ["COMPANIES_HOUSE_API_KEY"] = "x"
    ch_client.KEY = "x"


@respx.mock
def test_search_and_profile():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": [{"title": "ACME", "company_number": "123"}]}
    )
    data = ch_client.search_companies("ACME")
    assert data["items"][0]["company_number"] == "123"

    respx.get(f"{BASE}/company/123").respond(json={"company_number": "123"})
    prof = ch_client.get_company_profile("123")
    assert prof["company_number"] == "123"


@respx.mock
def test_officers_and_psc_counts():
    respx.get(f"{BASE}/company/1/officers?items_per_page=1").respond(
        json={"total_results": 5}
    )
    assert ch_client.get_officers_count("1") == 5

    respx.get(
        f"{BASE}/company/1/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 2})
    assert ch_client.get_psc_count("1") == 2
