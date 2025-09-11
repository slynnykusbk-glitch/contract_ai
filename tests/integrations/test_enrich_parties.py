import os
import respx
import httpx

import json
from contract_review_app.core.schemas import Party
from contract_review_app.integrations.service import (
    enrich_parties_with_companies_house,
    build_companies_meta,
)
from contract_review_app.integrations.companies_house import client

BASE = client.BASE


def setup_function():
    client._CACHE.clear()  # type: ignore
    client._LAST.clear()  # type: ignore
    os.makedirs("var", exist_ok=True)
    open("var/audit.log", "w", encoding="utf-8").close()
    os.environ["FEATURE_COMPANIES_HOUSE"] = "1"
    os.environ["COMPANIES_HOUSE_API_KEY"] = "x"
    client.KEY = "x"


@respx.mock
def test_party_with_number():
    respx.get(f"{BASE}/company/123").respond(json={"company_name": "ACME LTD", "company_number": "123"})
    p = Party(name="Acme Ltd", company_number="123")
    res = enrich_parties_with_companies_house([p])
    assert res[0].registry and res[0].registry.name == "ACME LTD"


@respx.mock
def test_party_without_number_best_match():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": [{"title": "ACME LTD", "company_number": "555"}]}, headers={"ETag": "s1"}
    )
    respx.get(f"{BASE}/company/555").respond(json={"company_name": "ACME LTD", "company_number": "555"})
    p = Party(name="Acme Ltd")
    res = enrich_parties_with_companies_house([p])
    assert res[0].registry and res[0].registry.number_or_duns == "555"
    assert res[0].company_number == "555"


@respx.mock
def test_audit_has_no_pii():
    respx.get(f"{BASE}/search/companies").respond(json={"items": []}, headers={"ETag": "e1"})
    enrich_parties_with_companies_house([Party(name="Secret Corp")])
    with open("var/audit.log", "r", encoding="utf-8") as fh:
        data = fh.read()
    assert "integration_call" in data
    assert "Secret" not in data


@respx.mock
def test_build_companies_meta():
    respx.get(f"{BASE}/company/123").respond(
        json={
            "company_name": "ACME LTD",
            "company_number": "123",
            "company_status": "active",
            "registered_office_address": {"postal_code": "EC1A1AA"},
        }
    )
    respx.get(f"{BASE}/company/123/officers?items_per_page=1").respond(json={"total_results": 5})
    respx.get(
        f"{BASE}/company/123/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 1})
    p = Party(name="Acme Ltd", company_number="123", address="Some St, EC1A 1AA")
    meta = build_companies_meta([p])
    assert meta[0]["matched"]["company_number"] == "123"
    assert meta[0]["verdict"] == "ok"


@respx.mock
def test_build_companies_meta_preserves_doc_data():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": [{"title": "ACME LTD", "company_number": "555"}]}, headers={"ETag": "s1"}
    )
    respx.get(f"{BASE}/company/555").respond(
        json={
            "company_name": "ACME LTD",
            "company_number": "555",
            "company_status": "active",
        }
    )
    respx.get(f"{BASE}/company/555/officers?items_per_page=1").respond(json={"total_results": 3})
    respx.get(
        f"{BASE}/company/555/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 2})
    doc_party = Party(name="Acme Ltd")
    enriched = enrich_parties_with_companies_house([Party(**doc_party.model_dump())])
    meta = build_companies_meta(enriched, doc_parties=[doc_party])
    assert meta[0]["from_document"]["number"] is None
    assert meta[0]["matched"]["company_number"] == "555"


@respx.mock
def test_blackrock_verdict_ok():
    fix = json.loads(open("tests/fixtures/ch_blackrock_profile.json", "r", encoding="utf-8").read())
    respx.get(f"{BASE}/company/02022650").respond(json=fix)
    respx.get(f"{BASE}/company/02022650/officers?items_per_page=1").respond(json={"total_results": 1})
    respx.get(
        f"{BASE}/company/02022650/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 0})
    p = Party(name="BLACK ROCK (UK) LIMITED", company_number="02022650")
    meta = build_companies_meta([p])
    assert meta[0]["verdict"] == "ok"
