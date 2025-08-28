from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from contract_review_app.rules_v2.adapter import (
    adapt_finding_v1_to_v2,
    run_legacy_rule,
)
from contract_review_app.rules_v2.models import FindingV2


def test_basic_mapping():
    v1 = {
        "code": "C1",
        "message": "msg",
        "severity_level": "warning",
        "evidence": "proof",
        "citations": [
            {"url": "http://example.com"},
            {"instrument": "Law", "section": "10"},
            "extra",
        ],
        "tags": ["t1", None, "t2"],
    }
    f2 = adapt_finding_v1_to_v2(v1, pack="pack", rule_id="rule")
    assert f2.id == "C1"
    assert f2.severity == "Medium"
    assert f2.evidence == ["proof"]
    assert f2.citation == ["http://example.com", "Law §10", "extra"]
    assert f2.flags == ["t1", "t2"]
    assert f2.title["en"] == "C1"
    assert f2.title["uk"] == "C1"
    assert f2.message["en"] == "msg"
    assert f2.message["uk"] == "msg"
    assert f2.category == "General"
    assert isinstance(f2.created_at, datetime)


class ObjV2:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def model_dump(self) -> Dict[str, Any]:
        return self._data


class ObjV1:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def dict(self) -> Dict[str, Any]:
        return self._data


def test_pydantic_like_objects():
    data = {"code": "X", "message": "mm"}
    for obj in [ObjV2(data), ObjV1(data)]:
        f2 = adapt_finding_v1_to_v2(obj, pack="p", rule_id="r")
        assert f2.id == "X"
        assert f2.message["en"] == "mm"


def test_string_input():
    f2 = adapt_finding_v1_to_v2("hello", pack="p", rule_id="r1")
    assert f2.id == "r1"
    assert f2.message["en"] == "hello"
    assert f2.message["uk"] == "hello"
    assert f2.severity == "Medium"


def test_run_legacy_rule_variants():
    def rule_single(ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"code": "S", "message": "one"}

    def rule_list(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"code": "A"}, {"code": "B"}]

    def rule_none(ctx: Dict[str, Any]) -> None:
        return None

    def rule_fail(ctx: Dict[str, Any]) -> None:
        raise ValueError("boom")

    out_single = run_legacy_rule(rule_single, {}, pack="p", rule_id="r1")
    assert len(out_single) == 1 and isinstance(out_single[0], FindingV2)

    out_list = run_legacy_rule(rule_list, {}, pack="p", rule_id="r2")
    assert [f.id for f in out_list] == ["A", "B"]

    out_none = run_legacy_rule(rule_none, {}, pack="p", rule_id="r3")
    assert out_none == []

    out_fail = run_legacy_rule(rule_fail, {}, pack="p", rule_id="r4")
    assert len(out_fail) == 1
    err = out_fail[0]
    assert err.severity == "High"
    assert "boom" in err.message["en"]
    assert err.flags == ["legacy", "error"]


def test_determinism():
    v1 = {"code": "D", "message": "m"}
    f2a = adapt_finding_v1_to_v2(v1, pack="p", rule_id="r")
    f2b = adapt_finding_v1_to_v2(v1, pack="p", rule_id="r")
    da = asdict(f2a)
    db = asdict(f2b)
    da.pop("created_at")
    db.pop("created_at")
    assert da == db
    assert isinstance(f2a.created_at, datetime)
