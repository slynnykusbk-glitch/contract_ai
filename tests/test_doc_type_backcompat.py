import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
from contract_review_app.api.app import app

client = TestClient(app)
SAMPLE = "CONFIDENTIALITY AGREEMENT\nThis Agreement is made..."

def test_analyze_has_both_flat_and_legacy_type():
    r = client.post("/api/analyze", json={"text": SAMPLE})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert isinstance(s.get("type"), str) and s["type"]
    assert "type_confidence" in s
    dt = s.get("doc_type") or {}
    top = dt.get("top") or {}
    assert isinstance(top.get("type"), str) and top["type"]
    assert "confidence" in dt
