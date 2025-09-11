from __future__ import annotations

"""Document type patterns for heuristic classification.

Each key maps to pattern data:
{
  "title_keywords": [...],
  "body_keywords": [...],
  "must_have_any": [...],           # optional
  "negative": [...],                # optional
  "boost_phrases": {phrase: weight} # optional
}
"""

from typing import Any, Dict, List

DOC_TYPE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "nda": {
        "title_keywords": [
            "non-disclosure",
            "confidentiality",
            "confidentiality agreement",
            "non-disclosure agreement",
            "mutual nda",
            "one-way nda",
        ],
        "body_keywords": [
            "confidential information",
            "disclosing party",
            "receiving party",
            "permitted purpose",
            "non-disclosure",
            "term of confidentiality",
            "return or destroy",
        ],
    },
    "msa_services": {
        "title_keywords": ["master services", "services agreement"],
        "body_keywords": [
            "services",
            "statement of work",
            "sow",
            "service levels",
            "sla",
            "change control",
            "acceptance criteria",
        ],
    },
    "supply_of_goods": {
        "title_keywords": ["supply agreement", "supply of goods", "supply contract"],
        "body_keywords": [
            "delivery",
            "risk and title",
            "incoterms",
            "specifications",
            "defects",
            "returns",
        ],
    },
    "dpa_uk_gdpr": {
        "title_keywords": ["data processing agreement", "dpa"],
        "body_keywords": [
            "controller",
            "processor",
            "uk gdpr",
            "data subject",
            "sub-processor",
            "international transfers",
            "annex",
        ],
    },
    "license_ip": {
        "title_keywords": ["licence", "license"],
        "body_keywords": [
            "grant of licence",
            "licensor",
            "licensee",
            "royalty",
            "territory",
            "ip ownership",
        ],
    },
    "distribution": {
        "title_keywords": ["distribution"],
        "body_keywords": [
            "distributor",
            "exclusive",
            "non-exclusive",
            "territory",
            "price list",
            "sell",
        ],
    },
    "reseller": {
        "title_keywords": ["reseller"],
        "body_keywords": [
            "reseller",
            "purchase",
            "sell",
            "price list",
            "territory",
        ],
    },
    "spa_shares": {
        "title_keywords": ["share purchase", "share sale"],
        "body_keywords": [
            "seller",
            "buyer",
            "sale of the entire issued share capital",
            "completion",
            "disclosure letter",
            "warranties",
            "indemnities",
        ],
    },
    "employment": {
        "title_keywords": ["employment"],
        "body_keywords": [
            "employer",
            "employee",
            "salary",
            "probationary period",
            "notice period",
            "holiday entitlement",
        ],
    },
    "loan": {
        "title_keywords": ["loan", "facility"],
        "body_keywords": [
            "borrower",
            "lender",
            "principal",
            "interest rate",
            "repayment",
            "events of default",
            "security",
        ],
    },
    "lease": {
        "title_keywords": ["lease", "tenancy"],
        "body_keywords": [
            "landlord",
            "tenant",
            "premises",
            "rent",
            "term",
            "repair",
            "insurance",
        ],
    },
    "saas_subscription": {
        "title_keywords": ["saas", "subscription", "cloud services"],
        "body_keywords": [
            "subscription",
            "cloud service",
            "availability",
            "uptime",
            "support",
            "user licence",
            "user license",
        ],
    },
    "consultancy": {
        "title_keywords": ["consultancy", "consulting"],
        "body_keywords": [
            "consultant",
            "deliverables",
            "fees",
            "day rate",
            "independent contractor",
            "ip assignment",
        ],
    },
    "settlement": {
        "title_keywords": ["settlement"],
        "body_keywords": [
            "full and final settlement",
            "waiver",
            "release",
            "claims",
            "without admission",
        ],
    },
    "shareholders": {
        "title_keywords": ["shareholders", "shareholder"],
        "body_keywords": [
            "reserved matters",
            "board",
            "drag",
            "tag",
            "dividends",
        ],
    },
    "joint_venture": {
        "title_keywords": ["joint venture"],
        "body_keywords": [
            "jv",
            "contribution of assets",
            "governance",
            "distribution of profits",
        ],
    },
    "framework_calloff": {
        "title_keywords": ["framework"],
        "body_keywords": [
            "call-off",
            "order procedure",
            "mini-competition",
        ],
    },
    "manufacturing": {
        "title_keywords": ["manufacturing"],
        "body_keywords": [
            "manufacture",
            "supply",
            "quality control",
            "specifications",
            "tooling",
        ],
    },
    "maintenance_support": {
        "title_keywords": ["maintenance", "support"],
        "body_keywords": [
            "support",
            "maintenance",
            "response time",
            "restore times",
            "p1",
            "p2",
            "updates",
            "patches",
        ],
    },
}

