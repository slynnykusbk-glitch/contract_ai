import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def _norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def test_analyze_offsets_match_snippets():
    text = "Confidential information shall remain secret."
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    data = r.json()
    findings = data.get("analysis", {}).get("findings") or data.get("findings") or data.get("issues") or []
    norm = _norm(text)
    for f in findings:
        start = f.get("start")
        end = f.get("end")
        snippet = _norm(f.get("snippet", ""))
        if isinstance(start, int) and isinstance(end, int) and snippet:
            assert norm[start:end] == snippet
