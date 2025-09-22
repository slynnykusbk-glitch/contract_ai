"""Canonical label taxonomy and resolver utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import Pattern


def _compile(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


SMART_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    for src, dst in SMART_REPLACEMENTS.items():
        normalized = normalized.replace(src, dst)
    normalized = normalized.replace("\u00A0", " ")
    normalized = normalized.replace("\u200D", "")
    normalized = re.sub(r"\biso\s*\(\s*27001\s*\)", "iso 27001", normalized, flags=re.IGNORECASE)
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


_SYNONYM_PATTERNS: dict[str, Pattern[str]] = {}


def _synonym_pattern(synonym: str) -> Pattern[str]:
    pattern = _SYNONYM_PATTERNS.get(synonym)
    if pattern is None:
        pattern = re.compile(rf"(?<!\\w){re.escape(synonym)}(?!\\w)")
        _SYNONYM_PATTERNS[synonym] = pattern
    return pattern


def _analysis_window(text: str, radius: int = 900) -> str:
    if len(text) <= radius * 2:
        return text
    head = text[:radius]
    tail = text[-radius:]
    separator = "\n"
    return head + separator + tail


_NUM = r"(?:\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fifteen|twenty|thirty|sixty|ninety)(?:\s*\(\d{1,3}\))?"
_DAY_QUAL = r"(?:(?:business|working|calendar)\s+)?"
_DAYS = r"days?"
_PAY_TRIG = r"(?:net|within|no\s+later\s+than|payable\s+within|due\s+within)"
PAYMENT_TERMS_PATTERN = rf"\b{_PAY_TRIG}\s+{_NUM}\s+{_DAY_QUAL}{_DAYS}\b"
PAYMENT_TERMS_REGEX = re.compile(PAYMENT_TERMS_PATTERN, re.IGNORECASE | re.UNICODE)


ISO27001_REGEX = re.compile(
    r"""
    \b
    iso
    (?:\s*/\s*iec)?
    \s*
    [\-/\s]?
    \(?\s*27001\s*\)?
    (?:\s*:\s*(?:2013|2017|2022))?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

SECURITY_INFORMATION_REGEXES = [
    ISO27001_REGEX,
    re.compile(r"\biso27001\b", re.IGNORECASE),
    re.compile(r"\biso\s*[/\-]?\s*iec\s*27001\b", re.IGNORECASE),
    re.compile(r"\binformation\s+security\b", re.IGNORECASE),
    re.compile(r"\bisms\b", re.IGNORECASE),
]


LABELS_CANON: dict[str, dict[str, object]] = {
    "parties": {
        "high_priority_synonyms": ["parties", "the parties", "definitions of parties"],
        "regex": [],
        "domains": set(),
    },
    "definitions": {
        "high_priority_synonyms": ["definitions", "interpretation – definitions"],
        "regex": [],
        "domains": set(),
    },
    "interpretation": {
        "high_priority_synonyms": ["interpretation", "construction", "rules of interpretation"],
        "regex": [],
        "domains": set(),
    },
    "term": {
        "high_priority_synonyms": ["term", "duration", "commencement and term"],
        "regex": [],
        "domains": set(),
    },
    "renewal_auto": {
        "high_priority_synonyms": ["auto-renewal", "renewal term", "automatic renewal"],
        "regex": [],
        "domains": set(),
    },
    "termination_convenience": {
        "high_priority_synonyms": ["termination for convenience", "without cause", "no-fault termination"],
        "regex": [],
        "domains": set(),
    },
    "termination_breach": {
        "high_priority_synonyms": ["termination for breach", "material breach", "cure period"],
        "regex": [],
        "domains": set(),
    },
    "termination_insolvency": {
        "high_priority_synonyms": ["insolvency", "bankruptcy", "winding-up", "administration"],
        "regex": [],
        "domains": set(),
    },
    "termination_change_of_control": {
        "high_priority_synonyms": ["change of control", "c.o.c."],
        "regex": [],
        "domains": set(),
    },
    "survival": {
        "high_priority_synonyms": ["survival", "surviving provisions"],
        "regex": [],
        "domains": set(),
    },
    "notices": {
        "high_priority_synonyms": [
            "service of notices",
            "addresses for notice",
            "notice shall be delivered",
        ],
        "regex": [],
        "domains": set(),
    },
    "governing_law": {
        "high_priority_synonyms": ["governing law", "laws of"],
        "regex": [],
        "domains": set(),
    },
    "jurisdiction": {
        "high_priority_synonyms": ["jurisdiction", "exclusive jurisdiction", "non-exclusive jurisdiction"],
        "regex": [],
        "domains": set(),
    },
    "dispute_resolution": {
        "high_priority_synonyms": [
            "dispute resolution",
            "disputes procedure",
            "escalation steps",
        ],
        "regex": [],
        "domains": set(),
    },
    "escalation": {
        "high_priority_synonyms": ["escalation procedure", "senior negotiation"],
        "regex": [],
        "domains": set(),
    },
    "mediation": {
        "high_priority_synonyms": ["mediation", "cedr", "adr"],
        "regex": [],
        "domains": set(),
    },
    "arbitration": {
        "high_priority_synonyms": ["arbitration", "lcia", "icc"],
        "regex": [],
        "domains": set(),
    },
    "assignment": {
        "high_priority_synonyms": [
            "assignment",
            "novation",
            "transfer of this agreement",
        ],
        "regex": [],
        "domains": set(),
    },
    "subcontracting": {
        "high_priority_synonyms": ["subcontract", "sub-contractors"],
        "regex": [],
        "domains": set(),
    },
    "variation": {
        "high_priority_synonyms": ["variation", "amendment", "change to this agreement"],
        "regex": [],
        "domains": set(),
    },
    "entire_agreement": {
        "high_priority_synonyms": ["entire agreement", "whole agreement"],
        "regex": [],
        "domains": set(),
    },
    "severance": {
        "high_priority_synonyms": ["severance", "invalidity"],
        "regex": [],
        "domains": set(),
    },
    "waiver": {
        "high_priority_synonyms": ["waiver", "no waiver"],
        "regex": [],
        "domains": set(),
    },
    "third_party_rights": {
        "high_priority_synonyms": ["third party rights", "contracts (rights of third parties) act 1999"],
        "regex": [],
        "domains": set(),
    },
    "confidentiality": {
        "high_priority_synonyms": ["confidentiality", "confidential information", "non-disclosure"],
        "regex": [],
        "domains": set(),
    },
    "permitted_disclosures": {
        "high_priority_synonyms": ["permitted disclosure", "required by law", "regulator"],
        "regex": [],
        "domains": set(),
    },
    "announcements_publicity": {
        "high_priority_synonyms": ["publicity", "announcements", "press release"],
        "regex": [],
        "domains": set(),
    },
    "force_majeure": {
        "high_priority_synonyms": ["force majeure", "excused performance"],
        "regex": [],
        "domains": set(),
    },
    "insurance_requirements": {
        "high_priority_synonyms": ["insurance", "insurances to be maintained"],
        "regex": [],
        "domains": set(),
    },
    "limitation_of_liability": {
        "high_priority_synonyms": [
            "limitation of liability",
            "limitation on liability",
            "exclusions of liability",
        ],
        "regex": [],
        "domains": set(),
    },
    "indirect_consequential_exclusion": {
        "high_priority_synonyms": ["indirect", "consequential", "loss of profit"],
        "regex": [],
        "domains": set(),
    },
    "liability_cap_amount": {
        "high_priority_synonyms": [
            "aggregate cap",
            "liability limit",
            "cap on liability",
            "liability cap",
        ],
        "regex": [
            _compile(r"cap(?: on)? liability.*?(?:£|gbp|usd|eur)\s*\d"),
            _compile(r"liability cap.*?(?:£|gbp|usd|eur)\s*\d"),
        ],
        "domains": set(),
    },
    "liability_carveouts": {
        "high_priority_synonyms": ["carve-out", "unlimited for", "excludes cap"],
        "regex": [],
        "domains": set(),
    },
    "indemnity_general": {
        "high_priority_synonyms": ["indemnify", "indemnity", "hold harmless"],
        "regex": [],
        "domains": set(),
    },
    "ip_indemnity": {
        "high_priority_synonyms": ["ipr indemnity", "infringement indemnity"],
        "regex": [],
        "domains": {"ip"},
    },
    "dp_indemnity": {
        "high_priority_synonyms": ["data protection indemnity"],
        "regex": [],
        "domains": {"dp"},
    },
    "set_off": {
        "high_priority_synonyms": ["set-off", "no setoff"],
        "regex": [],
        "domains": set(),
    },
    "payment_terms": {
        "high_priority_synonyms": [
            "payment terms",
            "invoice shall be paid",
            "due within",
        ],
        "regex": [
            PAYMENT_TERMS_REGEX,
            _compile(r"net\s+(?:thirty|sixty|\d+)[^a-z0-9]{0,5}\(\s*\d+\s*\)\s*day"),
            _compile(
                r"within\s+(?:[a-z]+|\d+)[^a-z0-9]{0,5}\(\s*\d+\s*\)\s*business\s+day"
            ),
        ],
        "domains": set(),
    },
    "late_payment_interest": {
        "high_priority_synonyms": [
            "interest on late payment",
            "late payment interest",
            "interest shall accrue",
        ],
        "regex": [_compile(r"base rate\s*\+\s*\d+(?:\.\d+)?%")],
        "domains": set(),
    },
    "price_changes_indexation": {
        "high_priority_synonyms": ["indexation", "rpi", "cpi", "price increase", "price adjustment"],
        "regex": [],
        "domains": set(),
    },
    "taxes_vat": {
        "high_priority_synonyms": ["vat", "taxes", "withholding"],
        "regex": [],
        "domains": set(),
    },
    "audit_rights": {
        "high_priority_synonyms": ["audit", "audit rights", "open book"],
        "regex": [],
        "domains": set(),
    },
    "records_retention": {
        "high_priority_synonyms": ["records", "retain", "retention period"],
        "regex": [],
        "domains": set(),
    },
    "change_control": {
        "high_priority_synonyms": ["change control", "change procedure", "variation form"],
        "regex": [],
        "domains": set(),
    },
    "service_levels_sla": {
        "high_priority_synonyms": [
            "service levels",
            "service level agreement",
            "kpi",
        ],
        "regex": [],
        "domains": {"it"},
    },
    "service_credits": {
        "high_priority_synonyms": [
            "service credits",
            "service credit",
            "credit calculation",
        ],
        "regex": [],
        "domains": {"it"},
    },
    "benchmarking": {
        "high_priority_synonyms": ["benchmark", "best value"],
        "regex": [],
        "domains": {"it"},
    },
    "acceptance_testing": {
        "high_priority_synonyms": [
            "acceptance testing",
            "acceptance criteria",
            "acceptance tests",
        ],
        "regex": [],
        "domains": set(),
    },
    "delivery": {
        "high_priority_synonyms": [
            "delivery",
            "delivery terms",
            "delivery timetable",
        ],
        "regex": [],
        "domains": set(),
    },
    "risk_and_title": {
        "high_priority_synonyms": ["risk and title", "passing of risk", "title transfer"],
        "regex": [],
        "domains": set(),
    },
    "warranty_conformity": {
        "high_priority_synonyms": [
            "warranty",
            "conformity with specifications",
            "quality warranty",
        ],
        "regex": [],
        "domains": set(),
    },
    "warranty_performance": {
        "high_priority_synonyms": ["performance warranty", "service warranty"],
        "regex": [],
        "domains": set(),
    },
    "warranty_ip_noninfringe": {
        "high_priority_synonyms": ["non-infringement warranty", "ip warranty"],
        "regex": [],
        "domains": {"ip"},
    },
    "remedies": {
        "high_priority_synonyms": ["remedies", "cumulative", "exclusive remedy"],
        "regex": [],
        "domains": set(),
    },
    "liquidated_damages": {
        "high_priority_synonyms": ["liquidated damages", "lds"],
        "regex": [],
        "domains": set(),
    },
    "security_information": {
        "high_priority_synonyms": ["information security", "security requirements", "iso27001", "cyber essentials"],
        "regex": SECURITY_INFORMATION_REGEXES,
        "domains": {"it", "dp"},
    },
    "business_continuity_bcp": {
        "high_priority_synonyms": ["business continuity", "bcp", "continuity plan"],
        "regex": [],
        "domains": {"it"},
    },
    "disaster_recovery": {
        "high_priority_synonyms": ["disaster recovery", "dr plan"],
        "regex": [],
        "domains": {"it"},
    },
    "step_in_rights": {
        "high_priority_synonyms": ["step-in rights"],
        "regex": [],
        "domains": {"public"},
    },
    "ip_ownership": {
        "high_priority_synonyms": ["intellectual property", "ownership of ipr", "background ip", "foreground ip"],
        "regex": [],
        "domains": {"ip"},
    },
    "license_grant": {
        "high_priority_synonyms": [
            "licence grant",
            "license grant",
            "scope of the licence",
            "licence territory",
        ],
        "regex": [],
        "domains": {"ip"},
    },
    "escrow": {
        "high_priority_synonyms": ["escrow", "source code escrow"],
        "regex": [],
        "domains": {"it"},
    },
    "open_source": {
        "high_priority_synonyms": ["open source", "foss", "ospo"],
        "regex": [],
        "domains": {"it"},
    },
    "return_or_destruction": {
        "high_priority_synonyms": ["return and destruction", "return/delete", "upon termination return"],
        "regex": [],
        "domains": set(),
    },
    "modern_slavery": {
        "high_priority_synonyms": ["modern slavery act", "slavery and human trafficking"],
        "regex": [],
        "domains": {"compliance"},
    },
    "anti_bribery": {
        "high_priority_synonyms": ["bribery act", "anti-bribery", "corruption", "abc"],
        "regex": [],
        "domains": {"compliance"},
    },
    "anti_tax_evasion": {
        "high_priority_synonyms": ["criminal finances act", "facilitation of tax evasion", "anti-tax evasion"],
        "regex": [],
        "domains": {"compliance"},
    },
    "sanctions_export_controls": {
        "high_priority_synonyms": ["sanctions", "export control", "restricted party"],
        "regex": [],
        "domains": {"compliance"},
    },
    "equality_diversity": {
        "high_priority_synonyms": ["equality", "diversity", "non-discrimination"],
        "regex": [],
        "domains": {"compliance"},
    },
    "health_and_safety": {
        "high_priority_synonyms": ["health and safety", "h&s"],
        "regex": [],
        "domains": {"compliance"},
    },
    "conflicts_of_interest": {
        "high_priority_synonyms": ["conflicts of interest", "conflict of interest"],
        "regex": [],
        "domains": {"compliance"},
    },
    "non_solicitation": {
        "high_priority_synonyms": ["non-solicitation", "no poach", "no poaching"],
        "regex": [],
        "domains": set(),
    },
    "tupe": {
        "high_priority_synonyms": ["tupe", "transfer of undertakings"],
        "regex": [],
        "domains": {"employment"},
    },
    "staff_vetting": {
        "high_priority_synonyms": ["vetting", "dbs", "background checks"],
        "regex": [],
        "domains": {"employment"},
    },
    "subprocessor_approval": {
        "high_priority_synonyms": ["sub-processor approval", "subprocessor consent"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_general": {
        "high_priority_synonyms": ["data protection", "uk gdpr", "data protection act"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_roles": {
        "high_priority_synonyms": ["controller", "processor", "sub-processor"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_instructions": {
        "high_priority_synonyms": ["process only on instructions", "documented instructions"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_lawful_basis": {
        "high_priority_synonyms": ["lawful basis", "legitimate interests", "consent"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_security_measures": {
        "high_priority_synonyms": ["security measures", "technical and organisational", "tom"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_breach_notification": {
        "high_priority_synonyms": ["personal data breach", "notify", "72 hours"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_audit": {
        "high_priority_synonyms": ["audit of processing", "inspection", "audit rights"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_dsr": {
        "high_priority_synonyms": ["data subject rights", "access", "rectification", "erasure"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_retention_deletion": {
        "high_priority_synonyms": ["retention", "deletion", "return/delete"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_dpia": {
        "high_priority_synonyms": ["dpia", "impact assessment"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_special_category": {
        "high_priority_synonyms": ["special category data", "criminal convictions"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_records_of_processing": {
        "high_priority_synonyms": ["records of processing", "ropa"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_subprocessing": {
        "high_priority_synonyms": ["sub-processing", "prior written consent"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_back_to_back": {
        "high_priority_synonyms": ["back-to-back", "flow down"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_international_transfers": {
        "high_priority_synonyms": ["international transfer", "idta", "sccs", "restricted transfer"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_localisation": {
        "high_priority_synonyms": ["data residency", "data localisation", "localization"],
        "regex": [],
        "domains": {"dp"},
    },
    "dp_security_reviews": {
        "high_priority_synonyms": ["security reviews", "review dates", "review frequency"],
        "regex": [],
        "domains": {"dp"},
    },
    "saas_uptime": {
        "high_priority_synonyms": ["availability", "uptime", "service availability"],
        "regex": [],
        "domains": {"it"},
    },
    "support_maintenance": {
        "high_priority_synonyms": ["support", "maintenance", "patches", "updates"],
        "regex": [],
        "domains": {"it"},
    },
    "change_management_it": {
        "high_priority_synonyms": ["change management", "release management"],
        "regex": [],
        "domains": {"it"},
    },
    "backup_restore": {
        "high_priority_synonyms": ["backup", "restore", "rpo", "rto"],
        "regex": [],
        "domains": {"it"},
    },
    "data_portability_export": {
        "high_priority_synonyms": ["data export", "portability", "formats"],
        "regex": [],
        "domains": {"it"},
    },
    "suspension": {
        "high_priority_synonyms": ["suspension", "suspend the service"],
        "regex": [],
        "domains": {"it"},
    },
    "termination_assistance": {
        "high_priority_synonyms": ["termination assistance", "exit assistance"],
        "regex": [],
        "domains": {"it"},
    },
    "onboarding_migration": {
        "high_priority_synonyms": ["onboarding", "migration services"],
        "regex": [],
        "domains": {"it"},
    },
    "acceptance_it": {
        "high_priority_synonyms": ["uat", "user acceptance", "uat testing"],
        "regex": [],
        "domains": {"it"},
    },
    "rate_card": {
        "high_priority_synonyms": ["rate card", "time and materials", "t&m rates"],
        "regex": [],
        "domains": {"commercial"},
    },
    "usage_limits": {
        "high_priority_synonyms": ["usage limits", "fair use", "quota"],
        "regex": [],
        "domains": {"it"},
    },
    "nhs_safeguarding": {
        "high_priority_synonyms": ["safeguarding", "vulnerable adults", "vulnerable children"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_patient_confidentiality": {
        "high_priority_synonyms": ["patient confidentiality", "clinical confidentiality"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_information_governance": {
        "high_priority_synonyms": ["information governance", "ig toolkit"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_cqc_compliance": {
        "high_priority_synonyms": ["cqc", "care quality commission"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_serious_incident": {
        "high_priority_synonyms": ["serious incident", "serious incident reporting"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_step_in": {
        "high_priority_synonyms": ["nhs step-in", "nhs step in rights"],
        "regex": [],
        "domains": {"nhs"},
    },
    "nhs_national_tariff": {
        "high_priority_synonyms": ["national tariff", "nhs pricing"],
        "regex": [],
        "domains": {"nhs"},
    },
    "foi": {
        "high_priority_synonyms": ["freedom of information", "foia"],
        "regex": [],
        "domains": {"public"},
    },
    "transparency_publication": {
        "high_priority_synonyms": ["transparency", "publication scheme"],
        "regex": [],
        "domains": {"public"},
    },
    "delivery_terms_incoterms": {
        "high_priority_synonyms": ["incoterms", "dap", "ddp", "fob", "cif", "exw"],
        "regex": [_compile(r"\b(dap|ddp|fob|cif|exw)\b")],
        "domains": {"procurement"},
    },
    "lead_times": {
        "high_priority_synonyms": ["lead time", "delivery schedule"],
        "regex": [],
        "domains": {"procurement"},
    },
    "quality_control_qc": {
        "high_priority_synonyms": ["quality control", "inspection"],
        "regex": [],
        "domains": {"procurement"},
    },
    "warranty_doas_rma": {
        "high_priority_synonyms": ["rma", "doa", "returns"],
        "regex": [],
        "domains": {"procurement"},
    },
    "packaging_labelling": {
        "high_priority_synonyms": ["packaging", "labelling", "labeling"],
        "regex": [],
        "domains": {"procurement"},
    },
    "most_favoured_customer": {
        "high_priority_synonyms": ["most favoured customer", "most favoured buyer", "mfn"],
        "regex": [],
        "domains": {"procurement"},
    },
    "open_book_pricing": {
        "high_priority_synonyms": ["open-book", "cost transparency", "open book pricing"],
        "regex": [],
        "domains": {"procurement"},
    },
    "spares_obsolescence": {
        "high_priority_synonyms": ["spares", "obsolescence", "end-of-life"],
        "regex": [],
        "domains": {"procurement"},
    },
    "tooling": {
        "high_priority_synonyms": ["tooling", "tooling ownership"],
        "regex": [],
        "domains": {"procurement"},
    },
    "title_retention_rot": {
        "high_priority_synonyms": ["retention of title", "rot", "title retention"],
        "regex": [],
        "domains": {"procurement"},
    },
    "hazardous_substances": {
        "high_priority_synonyms": ["hazardous", "reach", "rohs"],
        "regex": [],
        "domains": {"procurement"},
    },
    "tenancy_rent": {
        "high_priority_synonyms": ["rent", "rent amount", "monthly rent"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_deposit": {
        "high_priority_synonyms": ["deposit", "tenancy deposit scheme"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_repairs": {
        "high_priority_synonyms": ["repairs", "landlord obligations", "tenant obligations"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_quiet_enjoyment": {
        "high_priority_synonyms": ["quiet enjoyment"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_assignment_underlet": {
        "high_priority_synonyms": ["assignment", "underlet", "sublet"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_break_clause": {
        "high_priority_synonyms": ["break clause", "break date"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_dilapidations": {
        "high_priority_synonyms": ["dilapidations"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_service_charge": {
        "high_priority_synonyms": ["service charge"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_insurance": {
        "high_priority_synonyms": ["insurance rent", "tenant insurance"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "tenancy_rent_review": {
        "high_priority_synonyms": ["rent review", "rent indexation"],
        "regex": [],
        "domains": {"real_estate"},
    },
    "construction_programme": {
        "high_priority_synonyms": ["programme", "construction schedule"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_variations": {
        "high_priority_synonyms": ["variation", "change order"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_eot": {
        "high_priority_synonyms": ["extension of time", "eot"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_ld_delay": {
        "high_priority_synonyms": ["liquidated damages for delay", "delay damages"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_retention": {
        "high_priority_synonyms": ["retention", "retention fund"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_collateral_warranties": {
        "high_priority_synonyms": ["collateral warranty"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_defects_liability": {
        "high_priority_synonyms": ["defects liability", "defects liability period"],
        "regex": [],
        "domains": {"construction"},
    },
    "construction_health_safety_cdm": {
        "high_priority_synonyms": ["cdm regulations", "construction design and management"],
        "regex": [],
        "domains": {"construction"},
    },
    "joa_operator": {
        "high_priority_synonyms": ["operator", "operatorship"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_opcom": {
        "high_priority_synonyms": ["operating committee", "opcom"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_work_program_budget": {
        "high_priority_synonyms": ["work programme", "work program", "wp&b"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_authorisation_for_expenditure": {
        "high_priority_synonyms": [
            "authorisation for expenditure",
            "authorization for expenditure",
            "afe",
        ],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_sole_risk": {
        "high_priority_synonyms": ["sole risk", "sole risk operations"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_default_nonconsent": {
        "high_priority_synonyms": ["default", "non-consenting party", "nonconsent"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_lifting_allocation": {
        "high_priority_synonyms": ["lifting", "allocation", "offtake"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_joint_accounting": {
        "high_priority_synonyms": ["joint account", "accounting procedure"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_decommissioning": {
        "high_priority_synonyms": ["abandonment", "decommissioning"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_marketing": {
        "high_priority_synonyms": ["marketing", "hydrocarbon marketing"],
        "regex": [],
        "domains": {"energy"},
    },
    "joa_assignment_consent": {
        "high_priority_synonyms": ["assignment", "joa consent"],
        "regex": [],
        "domains": {"energy"},
    },
    "payment_security": {
        "high_priority_synonyms": ["performance bond", "parent guarantee", "payment security"],
        "regex": [],
        "domains": {"finance"},
    },
    "insurance_types_limits": {
        "high_priority_synonyms": ["employers' liability", "public liability", "professional indemnity"],
        "regex": [],
        "domains": {"finance"},
    },
    "waiver_of_subrogation": {
        "high_priority_synonyms": ["waiver of subrogation"],
        "regex": [],
        "domains": {"finance"},
    },
    "deductibles_limits": {
        "high_priority_synonyms": ["deductible", "self-insured retention"],
        "regex": [],
        "domains": {"finance"},
    },
}


def resolve_labels(text: str, heading: str | None) -> set[str]:
    candidates: list[str] = []
    if heading:
        candidates.append(_normalize(heading))
    if text:
        candidates.append(_normalize(_analysis_window(text)))

    resolved: set[str] = set()
    for label, config in LABELS_CANON.items():
        synonyms = [
            token
            for token in config.get("high_priority_synonyms", [])
            if isinstance(token, str) and token
        ]
        regexes = [
            pattern
            for pattern in config.get("regex", [])
            if isinstance(pattern, re.Pattern)
        ]

        found = False
        for haystack in candidates:
            if not haystack:
                continue
            for synonym in synonyms:
                if _synonym_pattern(synonym).search(haystack):
                    resolved.add(label)
                    found = True
                    break
            if found:
                break
            for pattern in regexes:
                if pattern.search(haystack):
                    resolved.add(label)
                    found = True
                    break
            if found:
                break

    return resolved

