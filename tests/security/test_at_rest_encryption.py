from importlib import reload

from cryptography.fernet import Fernet

from contract_review_app.security import secure_store


def test_secure_store_roundtrip(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CR_ATREST_KEY", key)
    reload(secure_store)
    path = tmp_path / "secret.bin"
    secure_store.secure_write(path, "hello")
    with open(path, "rb") as f:
        raw = f.read()
    assert b"hello" not in raw
    assert secure_store.secure_read(path).decode() == "hello"
