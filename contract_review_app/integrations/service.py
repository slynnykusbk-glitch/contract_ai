import os
import re
from typing import Any, Dict, List

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
                    address = (
                        ", ".join([str(v) for v in addr_dict.values() if v]) or None
                    )
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


# ---------------------------------------------------------------------------
# Company meta helpers
# ---------------------------------------------------------------------------


_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}")


def _extract_postcode(addr: str | None) -> str:
    if not addr:
        return ""
    m = _POSTCODE_RE.search(addr.upper())
    return m.group(0).replace(" ", "") if m else ""


def _verdict_for_party(p: Party, data: Dict[str, Any] | None) -> Dict[str, Any]:
    verdict = {"level": "ok", "reasons": []}
    if not data:
        verdict["level"] = "warn"
        verdict["reasons"].append("name_mismatch")
        return verdict

    status = (data.get("company_status") or "").lower()
    if status and status != "active":
        verdict["level"] = "block"
        verdict["reasons"].append("status_dissolved")

    reg_name = (data.get("company_name") or data.get("title") or "").lower()
    if p.name and reg_name and p.name.lower() != reg_name:
        if verdict["level"] != "block":
            verdict["level"] = "warn"
        verdict["reasons"].append("name_mismatch")

    doc_pc = _extract_postcode(p.address)
    reg_addr = data.get("registered_office_address") or {}
    reg_pc = ""
    if isinstance(reg_addr, dict):
        reg_pc = _extract_postcode(", ".join(str(v) for v in reg_addr.values() if v))
    else:
        reg_pc = _extract_postcode(str(reg_addr))
    if doc_pc and reg_pc and doc_pc != reg_pc:
        if verdict["level"] != "block":
            verdict["level"] = "warn"
        verdict["reasons"].append("postcode_mismatch")

    accounts = data.get("accounts") or {}
    if accounts.get("overdue") and verdict["level"] != "block":
        verdict["level"] = "warn"

    conf = data.get("confirmation_statement") or {}
    if conf.get("overdue") and verdict["level"] != "block":
        verdict["level"] = "warn"

    return verdict


def build_companies_meta(
    parties: List[Party], doc_parties: List[Party] | None = None
) -> List[Dict[str, Any]]:
    if os.getenv("FEATURE_COMPANIES_HOUSE", "0") != "1" or not ch_client.KEY:
        return []
    meta: List[Dict[str, Any]] = []
    for idx, p in enumerate(parties):
        src = doc_parties[idx] if doc_parties and idx < len(doc_parties) else p
        doc = {"name": src.name, "number": src.company_number}
        data: Dict[str, Any] | None = None
        try:
            if p.company_number:
                data = ch_client.get_company_profile(p.company_number)
            elif p.name:
                search = ch_client.search_companies(p.name)
                items = search.get("items") or []
                match = None
                for item in items:
                    name = item.get("title") or item.get("company_name")
                    if name and name.lower() == p.name.lower():
                        match = item
                        break
                if not match and items:
                    match = items[0]
                if match:
                    p.company_number = match.get("company_number") or p.company_number
                    data = ch_client.get_company_profile(p.company_number)
            if data and p.company_number:
                try:
                    data["officers_count"] = ch_client.get_officers_count(
                        p.company_number
                    )
                    data["psc_count"] = ch_client.get_psc_count(p.company_number)
                except Exception:
                    pass
        except Exception:
            data = None
        vobj = _verdict_for_party(p, data)
        if data is None:
            verdict = "not_found"
        elif vobj.get("level") == "ok":
            verdict = "ok"
        else:
            verdict = "mismatch"
        meta.append({"from_document": doc, "matched": data, "verdict": verdict})
    return meta
