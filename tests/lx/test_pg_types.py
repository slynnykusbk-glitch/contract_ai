from decimal import Decimal
import json

import pytest

from contract_review_app.core.lx_types import Duration, Money, ParamGraph, SourceRef


def test_money_currency_normalization():
    assert Money(amount=Decimal("10"), currency="$").currency == "USD"
    assert Money(amount="5", currency="gbp").currency == "GBP"
    with pytest.raises(ValueError):
        Money(amount=1, currency="bitcoin")


def test_param_graph_json_serialization():
    pg = ParamGraph(
        payment_term=Duration(days=30),
        cap=Money(amount=Decimal("1234.56"), currency="EUR"),
        survival_items={"confidentiality"},
        cross_refs=[("c1", "c2")],
        parties=[{"name": "Acme", "role": "seller"}],
        signatures=[{"name": "John Doe", "entity": "Acme"}],
        sources={
            "cap": SourceRef(clause_id="cl1", span=(0, 10)),
        },
    )

    dumped = json.loads(pg.model_dump_json())
    assert dumped["cap"]["amount"] == "1234.56"
    assert dumped["cap"]["currency"] == "EUR"
    assert sorted(dumped["survival_items"]) == ["confidentiality"]
    assert dumped["cross_refs"] == [["c1", "c2"]]
    assert dumped["sources"]["cap"]["clause_id"] == "cl1"
