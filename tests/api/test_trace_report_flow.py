import os
import uuid
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


client = TestClient(app)
headers = {"x-api-key": "k", "x-schema-version": SCHEMA_VERSION}


def test_trace_report_flow():
    r = client.post("/api/analyze", json={"text": "hi"}, headers=headers)
    assert r.status_code == 200
    cid = r.headers["X-Cid"]
    assert client.get(f"/api/trace/{cid}").status_code == 200
    assert client.get(f"/api/trace/{cid}.html").status_code == 200
    assert client.get(f"/api/report/{cid}.html").status_code == 200
    assert client.get(f"/api/report/{cid}.pdf").status_code == 501

    bad = uuid.uuid4().hex
    assert client.get(f"/api/trace/{bad}").status_code == 404
