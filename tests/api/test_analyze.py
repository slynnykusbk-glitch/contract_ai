import json
import logging
from importlib import reload
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import contract_review_app.security.secure_store as secure_store
import contract_review_app.core.audit as audit_module
import contract_review_app.api.app as app_module


def _make_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.chdir(tmp_path)
    reload(secure_store)
    reload(audit_module)
    reload(app_module)
    return TestClient(app_module.app)


def test_analyze_ok_without_atrest_key(tmp_path, monkeypatch, caplog):
    """DEV fallback: no key still results in 200 and plaintext audit log."""

    monkeypatch.delenv("CR_ATREST_KEY", raising=False)
    client = _make_client(monkeypatch, tmp_path)
    with caplog.at_level(logging.WARNING):
        resp = client.post("/api/analyze", json={"text": "hi", "language": "en"})
    assert resp.status_code == 200
    assert "CR_ATREST_KEY not set" in caplog.text
    raw = (Path("var") / "audit.log").read_bytes()
    assert b"{" in raw  # stored without encryption


def test_audit_encrypts_when_key_present(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CR_ATREST_KEY", key)
    client = _make_client(monkeypatch, tmp_path)
    resp = client.post("/api/analyze", json={"text": "hi", "language": "en"})
    assert resp.status_code == 200
    path = Path("var") / "audit.log"
    raw = path.read_bytes().strip()
    assert raw and b"{" not in raw
    decrypted = secure_store.secure_read(path)
    assert decrypted != raw
    json.loads(decrypted)

