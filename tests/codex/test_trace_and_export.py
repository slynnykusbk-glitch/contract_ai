from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def _h():
    return {"x-schema-version": SCHEMA_VERSION}


def _run_analyze(text: str = "Hello world"):
    r = client.post("/api/analyze", json={"text": text}, headers=_h())
    assert r.status_code == 200
    cid = r.headers.get("x-cid")
    assert cid
    return cid


def test_trace_ok_contract():
    cid = _run_analyze("Governing law: England and Wales")
    r = client.get(f"/api/trace/{cid}", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["cid"] == cid
    assert "created_at" in body
    assert body.get("analysis", {}).get("status") is not None
    assert "meta" in body
    assert body.get("schema_version") == SCHEMA_VERSION

    r_html = client.get(f"/api/report/{cid}.html", headers=_h())
    assert r_html.status_code == 200
    assert "text/html" in r_html.headers.get("content-type", "")
    assert b"Contract AI Report" in r_html.content


def test_trace_invalid_cid():
    r = client.get("/api/trace/____", headers=_h())
    assert r.status_code == 404


def test_export_pdf():
    cid = _run_analyze("sample text")
    r = client.get(f"/api/report/{cid}.pdf", headers=_h())
    if r.status_code == 501:
        assert "PDF export not enabled" in r.json().get("detail", "")
    else:
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert len(r.content) > 5 * 1024
