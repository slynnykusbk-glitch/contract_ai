import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[3]))
from contract_review_app.api.app import app
import os

os.environ.setdefault("CR_ATREST_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")


client = TestClient(app)


def test_analyze_ok():
    resp = client.post("/api/analyze", json={"text": "hi"})
    assert resp.status_code == 200


def test_analyze_empty_text():
    resp = client.post("/api/analyze", json={"text": "   "})
    assert resp.status_code == 422


def test_analyze_extra_field():
    resp = client.post("/api/analyze", json={"text": "hi", "extra": 1})
    assert resp.status_code == 422
