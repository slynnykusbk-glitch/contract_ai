import pytest


def _apply_ops(text: str, ops):
    result = text
    for op in sorted(ops, key=lambda o: o["start"], reverse=True):
        result = result[: op["start"]] + op["replacement"] + result[op["end"] :]
    return result


def test_idempotent_after_fix(api):
    text = open("tests/fixtures/nda_mini.txt", encoding="utf-8").read()
    r = api.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    findings = r.json()["analysis"]["findings"]
    fixable = next((f for f in findings if f.get("ops")), None)
    if not fixable:
        pytest.skip("no fixable finding with ops")
    patched = _apply_ops(text, fixable["ops"])
    r2 = api.post("/api/analyze", json={"text": patched})
    assert r2.status_code == 200
    rids = {f["rule_id"] for f in r2.json()["analysis"]["findings"]}
    assert fixable["rule_id"] not in rids
