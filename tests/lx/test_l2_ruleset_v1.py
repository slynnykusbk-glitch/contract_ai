from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict

import pytest

from contract_review_app.core.lx_types import Duration, Money, ParamGraph, SourceRef
from contract_review_app.legal_rules.constraints import (
    eval_constraints,
    load_constraints,
)


def _duration(days: int, kind: str = "calendar") -> Duration:
    return Duration(days=days, kind=kind)  # type: ignore[arg-type]


def _money(amount: str, currency: str) -> Money:
    return Money(amount=Decimal(amount), currency=currency)


def _source(clause: str) -> SourceRef:
    return SourceRef(clause_id=clause, span=(0, 10))


def make_pg(**overrides) -> ParamGraph:
    base = dict(
        payment_term=None,
        contract_term=None,
        grace_period=None,
        governing_law=None,
        jurisdiction=None,
        cap=None,
        contract_currency=None,
        notice_period=None,
        cure_period=None,
        survival_items=set(),
        cross_refs=[],
        parties=[],
        signatures=[],
        sources={},
        annex_refs=[],
        order_of_precedence=None,
        undefined_terms=[],
        numbering_gaps=[],
        doc_flags={},
    )
    base.update(overrides)
    return ParamGraph(**base)


VIOLATION_FACTORIES: Dict[str, Callable[[], ParamGraph]] = {
    "L2-001": lambda: make_pg(
        parties=[
            {"name": "Alpha Ltd", "ch_number": "12345678", "ch_name": "Beta Limited"},
            {"name": "Gamma Ltd", "ch_number": "23456789", "ch_name": "Gamma Limited"},
        ],
        sources={"parties": _source("P1")},
    ),
    "L2-002": lambda: make_pg(
        parties=[
            {
                "name": "Alpha Ltd",
                "addresses": [{"line1": "1 Main St", "city": "London"}],
            }
        ],
        sources={"parties": _source("P1"), "parties/addrs": _source("P1")},
    ),
    "L2-003": lambda: make_pg(
        parties=[{"name": "Alpha Limited"}],
        signatures=[{"entity": "Beta Plc", "date": "2024-01-01"}],
        sources={"signatures": _source("S1"), "preamble": _source("P0")},
    ),
    "L2-004": lambda: make_pg(
        signatures=[{"entity": "Alpha Limited"}],
        sources={"signatures": _source("S1")},
    ),
    "L2-005": lambda: make_pg(
        parties=[
            {"name": "Alpha Ltd", "ch_number": "12345678", "ch_name": "Alpha Limited"},
            {"name": "Beta Ltd", "ch_number": "87654321", "ch_name": "Gamma Limited"},
        ],
        sources={"parties": _source("P1")},
    ),
    "L2-010": lambda: make_pg(
        governing_law="England and Wales",
        jurisdiction="Courts of France",
        sources={"governing_law": _source("J1"), "jurisdiction": _source("J2")},
    ),
    "L2-011": lambda: make_pg(
        jurisdiction="The parties submit to the exclusive and non-exclusive jurisdiction of the courts",
        sources={"dispute": _source("D1")},
    ),
    "L2-012": lambda: make_pg(
        jurisdiction="Courts of England",
        sources={"governing_law": _source("J1"), "jurisdiction": _source("J2")},
    ),
    "L2-013": lambda: make_pg(
        jurisdiction="[Jurisdiction TBD]",
        sources={"jurisdiction": _source("J2")},
    ),
    "L2-020": lambda: make_pg(
        payment_term=_duration(90),
        contract_term=_duration(60),
        grace_period=_duration(0),
        sources={
            "payment_term": _source("F1"),
            "contract_term": _source("T1"),
            "grace_period": _source("T1"),
        },
    ),
    "L2-021": lambda: make_pg(
        notice_period=_duration(30),
        cure_period=_duration(10),
        sources={"notice_period": _source("N1"), "cure_period": _source("C1")},
    ),
    "L2-022": lambda: make_pg(
        payment_term=_duration(30, "calendar"),
        notice_period=_duration(5, "business"),
        sources={"durations": _source("DUR")},
    ),
    "L2-023": lambda: make_pg(
        payment_term=_duration(30),
        sources={"payment_term": _source("F1"), "contract_term": _source("T1")},
    ),
    "L2-024": lambda: make_pg(
        notice_period=_duration(15),
        sources={"notice_period": _source("N1"), "cure_period": _source("C1")},
    ),
    "L2-030": lambda: make_pg(
        cap=_money("-1000", "GBP"),
        sources={"cap": _source("L1")},
    ),
    "L2-031": lambda: make_pg(
        cap=_money("1000", "USD"),
        contract_currency="GBP",
        sources={"cap": _source("L1"), "contract_currency": _source("CC")},
    ),
    "L2-032": lambda: make_pg(
        doc_flags={"indemnity_unlimited_no_carveout": True},
        sources={"indemnity": _source("I1")},
    ),
    "L2-033": lambda: make_pg(
        doc_flags={"fraud_exclusion_detected": True},
        sources={"liability": _source("I2")},
    ),
    "L2-034": lambda: make_pg(
        doc_flags={"cap_amount_missing": True}, sources={"cap": _source("L1")}
    ),
    "L2-040": lambda: make_pg(
        doc_flags={"public_domain_by_recipient": True},
        sources={"confidentiality": _source("C1")},
    ),
    "L2-041": lambda: make_pg(
        doc_flags={"illegal_possession_exception": True},
        sources={"confidentiality": _source("C1")},
    ),
    "L2-042": lambda: make_pg(
        doc_flags={"purpose_overbreadth": True},
        sources={"confidentiality": _source("C1")},
    ),
    "L2-043": lambda: make_pg(
        doc_flags={"return_delete_broken_ref": True},
        sources={"confidentiality": _source("C1")},
    ),
    "L2-044": lambda: make_pg(
        doc_flags={"missing_return_timeline": True},
        sources={"confidentiality": _source("C1")},
    ),
    "L2-050": lambda: make_pg(
        doc_flags={"notify_notwithstanding_law": True},
        sources={"regulatory": _source("R1")},
    ),
    "L2-051": lambda: make_pg(
        doc_flags={"overbroad_regulator_disclosure": True},
        sources={"regulatory": _source("R1")},
    ),
    "L2-052": lambda: make_pg(
        doc_flags={"regulator_notice_requires_consent": True},
        sources={"regulatory": _source("R1")},
    ),
    "L2-053": lambda: make_pg(
        doc_flags={"aml_obligations_missing": True}, sources={"aml": _source("A1")}
    ),
    "L2-060": lambda: make_pg(
        doc_flags={"fm_no_payment_carveout": True},
        sources={"force_majeure": _source("FM")},
    ),
    "L2-061": lambda: make_pg(
        doc_flags={"fm_financial_hardship": True},
        sources={"force_majeure": _source("FM")},
    ),
    "L2-070": lambda: make_pg(
        doc_flags={"pd_without_dp_obligations": True},
        sources={"data_protection": _source("DP")},
    ),
    "L2-071": lambda: make_pg(
        doc_flags={"data_transfer_without_safeguards": True},
        sources={"data_protection": _source("DP")},
    ),
    "L2-080": lambda: make_pg(
        undefined_terms=["Effective Date"], sources={"definitions": _source("DEF")}
    ),
    "L2-081": lambda: make_pg(
        numbering_gaps=[5], doc_flags={}, sources={"definitions": _source("DEF")}
    ),
    "L2-082": lambda: make_pg(
        annex_refs=["Schedule 1"],
        order_of_precedence=False,
        sources={"annexes": _source("ANN")},
    ),
    "L2-083": lambda: make_pg(
        doc_flags={"annex_reference_unresolved": True},
        sources={"annexes": _source("ANN")},
    ),
    "L2-084": lambda: make_pg(
        doc_flags={"broken_cross_references": True},
        sources={"cross_refs": _source("CR")},
    ),
    "L2-090": lambda: make_pg(
        doc_flags={"companies_act_1985_reference": True},
        sources={"statutes": _source("ST")},
    ),
    "L2-091": lambda: make_pg(
        doc_flags={"outdated_ico_reference": True}, sources={"statutes": _source("ST")}
    ),
    "L2-092": lambda: make_pg(
        doc_flags={"outdated_fsa_reference": True}, sources={"statutes": _source("ST")}
    ),
    "L2-100": lambda: make_pg(
        doc_flags={"fee_for_nda": True}, sources={"commercial": _source("COM")}
    ),
    "L2-101": lambda: make_pg(
        doc_flags={"shall_be_avoided_wording": True},
        sources={"commercial": _source("COM")},
    ),
    "L2-102": lambda: make_pg(
        survival_items={"governing law"}, sources={"survival": _source("SUR")}
    ),
}


COMPLIANT_FACTORIES: Dict[str, Callable[[], ParamGraph]] = {
    "L2-001": lambda: make_pg(
        parties=[
            {"name": "Alpha Ltd", "ch_number": "12345678", "ch_name": "Alpha Limited"},
            {"name": "Gamma Ltd", "ch_number": "23456789", "ch_name": "Gamma Limited"},
        ]
    ),
    "L2-002": lambda: make_pg(
        parties=[
            {
                "name": "Alpha Ltd",
                "addresses": [
                    {"line1": "1 Main St", "city": "London", "country": "UK"}
                ],
            }
        ]
    ),
    "L2-003": lambda: make_pg(
        parties=[{"name": "Alpha Limited"}],
        signatures=[{"entity": "Alpha Ltd", "date": "2024-01-01"}],
    ),
    "L2-004": lambda: make_pg(
        signatures=[{"entity": "Alpha Limited", "date": "2024-01-01"}]
    ),
    "L2-005": lambda: make_pg(
        parties=[
            {"name": "Alpha Ltd", "ch_number": "12345678", "ch_name": "Alpha Limited"},
            {"name": "Beta Ltd", "ch_number": "87654321", "ch_name": "Beta Limited"},
        ]
    ),
    "L2-010": lambda: make_pg(
        governing_law="England and Wales",
        jurisdiction="Courts of England and Wales",
    ),
    "L2-011": lambda: make_pg(
        jurisdiction="The parties submit to the exclusive jurisdiction of the courts"
    ),
    "L2-012": lambda: make_pg(
        governing_law="England and Wales", jurisdiction="Courts of England"
    ),
    "L2-013": lambda: make_pg(jurisdiction="Courts of England"),
    "L2-020": lambda: make_pg(
        payment_term=_duration(60),
        contract_term=_duration(90),
        grace_period=_duration(15),
    ),
    "L2-021": lambda: make_pg(notice_period=_duration(10), cure_period=_duration(15)),
    "L2-022": lambda: make_pg(
        payment_term=_duration(30, "business"), cure_period=_duration(5, "business")
    ),
    "L2-023": lambda: make_pg(payment_term=_duration(30), contract_term=_duration(60)),
    "L2-024": lambda: make_pg(notice_period=_duration(10), cure_period=_duration(10)),
    "L2-030": lambda: make_pg(cap=_money("1000", "GBP")),
    "L2-031": lambda: make_pg(cap=_money("1000", "GBP"), contract_currency="GBP"),
    "L2-032": lambda: make_pg(doc_flags={"indemnity_unlimited_no_carveout": False}),
    "L2-033": lambda: make_pg(doc_flags={"fraud_exclusion_detected": False}),
    "L2-034": lambda: make_pg(doc_flags={"cap_amount_missing": False}),
    "L2-040": lambda: make_pg(doc_flags={"public_domain_by_recipient": False}),
    "L2-041": lambda: make_pg(doc_flags={"illegal_possession_exception": False}),
    "L2-042": lambda: make_pg(doc_flags={"purpose_overbreadth": False}),
    "L2-043": lambda: make_pg(doc_flags={"return_delete_broken_ref": False}),
    "L2-044": lambda: make_pg(doc_flags={"missing_return_timeline": False}),
    "L2-050": lambda: make_pg(doc_flags={"notify_notwithstanding_law": False}),
    "L2-051": lambda: make_pg(doc_flags={"overbroad_regulator_disclosure": False}),
    "L2-052": lambda: make_pg(doc_flags={"regulator_notice_requires_consent": False}),
    "L2-053": lambda: make_pg(doc_flags={"aml_obligations_missing": False}),
    "L2-060": lambda: make_pg(doc_flags={"fm_no_payment_carveout": False}),
    "L2-061": lambda: make_pg(doc_flags={"fm_financial_hardship": False}),
    "L2-070": lambda: make_pg(doc_flags={"pd_without_dp_obligations": False}),
    "L2-071": lambda: make_pg(doc_flags={"data_transfer_without_safeguards": False}),
    "L2-080": lambda: make_pg(undefined_terms=[]),
    "L2-081": lambda: make_pg(numbering_gaps=[], doc_flags={"dangling_or": False}),
    "L2-082": lambda: make_pg(annex_refs=["Schedule 1"], order_of_precedence=True),
    "L2-083": lambda: make_pg(doc_flags={"annex_reference_unresolved": False}),
    "L2-084": lambda: make_pg(doc_flags={"broken_cross_references": False}),
    "L2-090": lambda: make_pg(doc_flags={"companies_act_1985_reference": False}),
    "L2-091": lambda: make_pg(doc_flags={"outdated_ico_reference": False}),
    "L2-092": lambda: make_pg(doc_flags={"outdated_fsa_reference": False}),
    "L2-100": lambda: make_pg(doc_flags={"fee_for_nda": False}),
    "L2-101": lambda: make_pg(doc_flags={"shall_be_avoided_wording": False}),
    "L2-102": lambda: make_pg(
        survival_items={"Confidentiality", "Intellectual Property", "Liability"}
    ),
}


CONSTRAINT_MAP = {constraint.id: constraint for constraint in load_constraints()}


@pytest.mark.parametrize("rule_id", sorted(VIOLATION_FACTORIES))
def test_l2_ruleset_detects_violation(rule_id: str) -> None:
    constraint = CONSTRAINT_MAP[rule_id]
    pg = VIOLATION_FACTORIES[rule_id]()
    findings, _ = eval_constraints(pg, [])
    matches = [finding for finding in findings if finding.rule_id == f"L2::{rule_id}"]
    assert matches, f"Expected finding for {rule_id}"
    finding = matches[0]
    assert finding.severity == constraint.severity
    assert finding.message.startswith(constraint.message_tmpl)


@pytest.mark.parametrize("rule_id", sorted(COMPLIANT_FACTORIES))
def test_l2_ruleset_allows_compliant_case(rule_id: str) -> None:
    pg = COMPLIANT_FACTORIES[rule_id]()
    findings, _ = eval_constraints(pg, [])
    assert all(finding.rule_id != f"L2::{rule_id}" for finding in findings)
