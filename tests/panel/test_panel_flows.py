from pathlib import Path
import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)


def _headers():
    headers = {"x-schema-version": "1.3"}
    flag = os.getenv("FEATURE_REQUIRE_API_KEY", "").strip().lower()
    if flag in {"1", "true", "yes", "on", "enabled"}:
        headers["x-api-key"] = os.getenv("API_KEY", "")
    return headers


def _apply_ops(text: str, ops):
    result = text
    for op in sorted(ops, key=lambda o: o["start"], reverse=True):
        result = result[: op["start"]] + op["replacement"] + result[op["end"] :]
    return result


def test_panel_end_to_end_flow():
    # Step 1: analyze mini NDA
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "nda_mini.txt"
    text = fixture.read_text(encoding="utf-8")
    r = client.post(
        "/api/analyze",
        json={"text": text, "language": "en-GB"},
        headers=_headers(),
    )
    assert r.status_code == 200
    findings = r.json()["analysis"]["findings"]
    assert findings
    norm_text = text.replace("\r\n", "\n").replace("\r", "\n")
    valid = 0
    for f in findings:
        start = f["start"]
        end = f["end"]
        snippet = f["snippet"].replace("\r\n", "\n").replace("\r", "\n")
        assert 0 <= start <= end <= len(norm_text)
        if norm_text[start:end] == snippet:
            valid += 1
    assert valid >= 1

    # Step 2: draft
    payload = {
        "text": "Ping",
        "mode": "friendly",
        "before_text": "",
        "after_text": "",
        "language": "en-GB",
    }
    r = client.post("/api/gpt-draft", json=payload, headers=_headers())
    assert r.status_code == 200
    data = r.json()
    assert data.get("proposed_text", "").strip() != ""

    # Step 3: suggest edits
    original = "bad clause"
    r = client.post(
        "/api/suggest_edits",
        json={"text": original, "language": "en-GB"},
        headers=_headers(),
    )
    assert r.status_code == 200
    sugg = r.json()
    proposed = sugg.get("proposed_text", "")
    ops = sugg.get("ops", [])
    if proposed and proposed != original:
        assert ops, "ops should describe edits"
        patched = _apply_ops(original, ops)
        assert patched == proposed
