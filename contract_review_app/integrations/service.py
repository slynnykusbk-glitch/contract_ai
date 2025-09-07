import os
from typing import List

from contract_review_app.core.schemas import Party, CompanyProfile
from contract_review_app.integrations.companies_house import client as ch_client


def enrich_parties_with_companies_house(parties: List[Party]) -> List[Party]:
    if os.getenv("FEATURE_COMPANIES_HOUSE", "0") != "1" or not ch_client.KEY:
        return parties
    enriched: List[Party] = []
    for p in parties:
        try:
            data = None
            if p.company_number:
                data = ch_client.get_company_profile(p.company_number)
            else:
                if not p.name:
                    enriched.append(p)
                    continue
                search = ch_client.search_companies(p.name)
                items = search.get("items") or []
                match = None
                for item in items:
                    name = item.get("title") or item.get("company_name")
                    if name and p.name and name.lower() == p.name.lower():
                        match = item
                        break
                if not match and items:
                    match = items[0]
                if match:
                    p.company_number = match.get("company_number")
                    data = ch_client.get_company_profile(p.company_number)
            if data:
                addr_dict = data.get("registered_office_address") or {}
                address = None
                if isinstance(addr_dict, dict):
                    address = ", ".join([str(v) for v in addr_dict.values() if v]) or None
                profile = CompanyProfile(
                    name=data.get("company_name") or data.get("title"),
                    number_or_duns=data.get("company_number"),
                    status=data.get("company_status"),
                    address=address,
                    incorp_date=data.get("date_of_creation"),
                    sic_codes=data.get("sic_codes") or [],
                )
                p.registry = profile
                p.address = p.address or profile.address
                if not p.company_number:
                    p.company_number = profile.number_or_duns
        except Exception:
            pass
        enriched.append(p)
    return enriched
