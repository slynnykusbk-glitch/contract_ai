import os
from types import SimpleNamespace
from fastapi.testclient import TestClient
import contract_review_app.api.app as app_module
from contract_review_app.api.app import app


def _h():
    return {"x-api-key": os.environ.get("API_KEY", "local-test-key-123"), "x-schema-version": "1.3"}


def _patch(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "local-test-key-123")


def test_one_of_ok_citations(monkeypatch):
    _patch(monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/citation/resolve", json={"citations": [{"instrument": "ACT", "section": "1"}]}, headers=_h())
        assert r.status_code == 200
        assert r.json()["citations"][0]["instrument"] == "ACT"


def test_one_of_ok_findings(monkeypatch):
    _patch(monkeypatch)
    def fake_resolve(f):
        return SimpleNamespace(instrument="ACT", section="1")
    monkeypatch.setattr(app_module, "resolve_citation", fake_resolve)
    with TestClient(app) as c:
        r = c.post("/api/citation/resolve", json={"findings": [{"message": "x"}]}, headers=_h())
        assert r.status_code == 200
        assert r.json()["citations"][0]["section"] == "1"


def test_both_or_none_400_message(monkeypatch):
    _patch(monkeypatch)
    with TestClient(app) as c:
        r1 = c.post("/api/citation/resolve", json={}, headers=_h())
        assert r1.status_code == 400
        assert r1.json()["detail"] == "Exactly one of findings or citations is required"
        r2 = c.post("/api/citation/resolve", json={"citations": [], "findings": []}, headers=_h())
        assert r2.status_code == 400
        assert r2.json()["detail"] == "Exactly one of findings or citations is required"
