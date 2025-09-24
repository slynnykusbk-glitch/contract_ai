from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet


class _NoopCipher:
    """Identity cipher used when encryption key is missing in dev."""

    def encrypt(self, data: bytes) -> bytes:  # pragma: no cover - trivial
        return data

    def decrypt(self, token: bytes) -> bytes:  # pragma: no cover - trivial
        return token


_cipher: Fernet | _NoopCipher | None = None


def _get_cipher() -> Fernet | _NoopCipher:
    global _cipher
    if _cipher is not None:
        return _cipher
    key = os.getenv("CR_ATREST_KEY")
    if not key:
        if os.getenv("ENV", "dev").lower() != "prod":
            logging.warning(
                "CR_ATREST_KEY not set; audit log will be stored in plaintext"
            )
            _cipher = _NoopCipher()
            return _cipher
        raise RuntimeError("CR_ATREST_KEY not set")
    # assume key is standard Fernet key (base64 urlsafe)
    _cipher = Fernet(key)
    return _cipher


def secure_write(path: str | Path, data: bytes | str, *, append: bool = False) -> None:
    """Encrypt ``data`` and write to ``path``."""
    cipher = _get_cipher()
    if isinstance(data, str):
        data = data.encode("utf-8")
    token = cipher.encrypt(data)
    mode = "ab" if append else "wb"
    with open(path, mode) as f:
        f.write(token + b"\n")


def secure_read(path: str | Path) -> bytes:
    """Read and decrypt data previously written with ``secure_write``."""
    cipher = _get_cipher()
    with open(path, "rb") as f:
        lines = f.read().splitlines()
    out: bytearray = bytearray()
    for line in lines:
        if line:
            out.extend(cipher.decrypt(line))
    return bytes(out)


__all__ = ["secure_write", "secure_read"]
