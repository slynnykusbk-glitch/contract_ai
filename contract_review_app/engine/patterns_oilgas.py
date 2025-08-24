# contract_review_app/engine/patterns_oilgas.py
from __future__ import annotations

from typing import Dict, List

# Deterministic patterns for UK Oil & Gas Master Services Agreements (MSA) and Call-Offs.
# Each clause_type maps to a structure:
#   {"keywords": [...], "headers": [...], "aliases": [...]}
# - keywords: lowercase, token-oriented hints found in body text
# - headers: canonical or near-canonical clause headings as they appear in UK O&G contracts
# - aliases: alternative names/common variants used across operators and contractors
#
# NOTE: This module is pure data (no I/O, no FastAPI). Ordering is deterministic.

CLAUSE_PATTERNS: Dict[str, dict] = {
    "term": {
        "keywords": [
            "commencement date",
            "effective date",
            "initial term",
            "extension period",
            "expiry",
            "renewal",
            "duration",
            "evergreen",
        ],
        "headers": [
            "TERM AND COMMENCEMENT",
            "DURATION AND RENEWAL",
            "COMMENCEMENT AND TERM",
        ],
        "aliases": ["term", "duration", "renewal_and_expiry"],
    },
    "call_off": {
        "keywords": [
            "call-off",
            "release order",
            "work order",
            "purchase order",
            "call off procedure",
            "call-off process",
            "scheduling",
            "mobilisation notice",
        ],
        "headers": [
            "CALL-OFF PROCEDURE",
            "WORK ORDERS AND RELEASES",
            "CALL-OFFS AND SCHEDULING",
        ],
        "aliases": ["call_offs", "call_off_procedure", "work_orders", "releases"],
    },
    "representatives": {
        "keywords": [
            "authorised representative",
            "company representative",
            "contractor representative",
            "contract manager",
            "contacts",
            "notice to representative",
        ],
        "headers": [
            "REPRESENTATIVES AND CONTRACT MANAGEMENT",
            "CONTRACT MANAGEMENT",
            "APPOINTED REPRESENTATIVES",
        ],
        "aliases": ["contract_management", "authorised_representatives"],
    },
    "performance_of_work": {
        "keywords": [
            "scope of work",
            "method statements",
            "deliverables",
            "programme",
            "milestones",
            "performance of the services",
            "execution of work",
            "work packs",
        ],
        "headers": [
            "PERFORMANCE OF THE WORK",
            "EXECUTION OF THE SERVICES",
            "SCOPE AND PERFORMANCE",
        ],
        "aliases": ["scope_of_work", "services_performance", "execution"],
    },
    "hse": {
        "keywords": [
            "health safety environment",
            "hse",
            "safe systems of work",
            "permit to work",
            "life saving rules",
            "cdm regulations",
            "riddor",
            "hazard",
            "authority to stop work",
        ],
        "headers": [
            "HEALTH, SAFETY AND ENVIRONMENT",
            "HSE REQUIREMENTS",
            "SAFETY AND ENVIRONMENT",
        ],
        "aliases": ["health_safety_environment", "safety_environment", "hse_requirements"],
    },
    "quality": {
        "keywords": [
            "quality plan",
            "quality assurance",
            "iso 9001",
            "inspection and test plan",
            "itp",
            "non-conformance",
            "factory acceptance test",
            "fat",
            "quality records",
        ],
        "headers": [
            "QUALITY MANAGEMENT",
            "QUALITY ASSURANCE AND CONTROL",
            "QUALITY REQUIREMENTS",
        ],
        "aliases": ["quality_assurance", "qa_qc", "quality_control"],
    },
    "variations": {
        "keywords": [
            "variation order",
            "change order",
            "change control",
            "contract amendment",
            "site instruction",
            "compensation event",
        ],
        "headers": [
            "VARIATIONS AND CHANGE CONTROL",
            "CHANGES TO THE WORK",
            "CHANGE MANAGEMENT",
        ],
        "aliases": ["changes", "change_control", "variation_orders"],
    },
    "pricing_payment": {
        "keywords": [
            "day rates",
            "rate schedule",
            "timesheets",
            "payment terms",
            "invoice",
            "late payment",
            "milestone payment",
            "retention",
            "set-off",
        ],
        "headers": [
            "PRICING AND PAYMENT",
            "PAYMENT TERMS",
            "RATES AND INVOICING",
        ],
        "aliases": ["payment", "pricing", "rates_and_payment"],
    },
    "taxes": {
        "keywords": [
            "withholding tax",
            "vat",
            "value added tax",
            "customs duties",
            "import duty",
            "tax indemnity",
            "permanent establishment",
        ],
        "headers": [
            "TAXES AND DUTIES",
            "TAXATION",
            "VAT AND TAXES",
        ],
        "aliases": ["taxation", "duties", "vat_taxes"],
    },
    "ip_rights": {
        "keywords": [
            "intellectual property",
            "ip rights",
            "background ip",
            "foreground ip",
            "licence",
            "moral rights",
            "software",
            "know-how",
        ],
        "headers": [
            "INTELLECTUAL PROPERTY RIGHTS",
            "IP AND LICENSING",
            "INTELLECTUAL PROPERTY",
        ],
        "aliases": ["intellectual_property", "ipr", "ip"],
    },
    "title": {
        "keywords": [
            "title to goods",
            "passing of title",
            "title retention",
            "retention of title",
            "delivery duty paid",
            "incoterms 2020",
        ],
        "headers": [
            "TITLE TO GOODS",
            "PASSING OF TITLE",
            "TITLE AND DELIVERY",
        ],
        "aliases": ["passing_of_title", "title_to_goods"],
    },
    "risk_structure": {
        "keywords": [
            "risk and title",
            "risk passes on delivery",
            "care custody and control",
            "cccc",
            "risk allocation",
            "loss of or damage to",
        ],
        "headers": [
            "RISK AND TITLE",
            "RISK OF LOSS",
            "RISK ALLOCATION",
        ],
        "aliases": ["risk", "risk_of_loss", "risk_allocation"],
    },
    "insurance": {
        "keywords": [
            "public liability",
            "employers' liability",
            "professional indemnity",
            "pi insurance",
            "insurance certificates",
            "subrogation waiver",
            "limit of indemnity",
        ],
        "headers": [
            "INSURANCE",
            "INSURANCE REQUIREMENTS",
            "INSURANCES",
        ],
        "aliases": ["insurances", "insurance_requirements"],
    },
    "warranty": {
        "keywords": [
            "warranty period",
            "defects liability",
            "repair or replace",
            "fitness for purpose",
            "merchantable quality",
            "warranty remedies",
        ],
        "headers": [
            "WARRANTIES",
            "WARRANTY AND REMEDIES",
            "DEFECTS LIABILITY",
        ],
        "aliases": ["warranties", "defects_liability"],
    },
    "anti_bribery": {
        "keywords": [
            "bribery act 2010",
            "anti-corruption",
            "facilitation payment",
            "ethics",
            "modern slavery",
            "ukba",
            "fraud and dishonesty",
        ],
        "headers": [
            "APPLICABLE LAWS, ETHICS AND ANTI-BRIBERY",
            "ANTI-BRIBERY AND CORRUPTION",
            "COMPLIANCE WITH LAWS AND ETHICS",
        ],
        "aliases": ["ethics", "anti_corruption", "uk_bribery_act"],
    },
    "export_control": {
        "keywords": [
            "export control compliance",
            "uk strategic export",
            "sanctions",
            "uk sanctions list",
            "us export administration regulations",
            "itar",
            "dual-use",
        ],
        "headers": [
            "EXPORT CONTROL COMPLIANCE",
            "TRADE CONTROLS AND SANCTIONS",
            "EXPORTS AND SANCTIONS",
        ],
        "aliases": ["sanctions", "trade_controls", "export_controls"],
    },
    "liens_claims": {
        "keywords": [
            "liens",
            "encumbrances",
            "claims",
            "title free and clear",
            "lien waiver",
        ],
        "headers": [
            "LIENS AND CLAIMS",
            "FREEDOM FROM LIENS",
            "CLAIMS AND LIENS",
        ],
        "aliases": ["liens", "claims_and_liens"],
    },
    "force_majeure": {
        "keywords": [
            "force majeure",
            "beyond reasonable control",
            "epidemic",
            "pandemic",
            "act of government",
            "relief from performance",
            "suspension due to fm",
        ],
        "headers": [
            "FORCE MAJEURE",
            "RELIEF EVENTS",
            "EXCUSING CAUSES",
        ],
        "aliases": ["fm", "relief_events"],
    },
    "confidentialit
