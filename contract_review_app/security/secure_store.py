from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is not None:
        return _cipher
    key = os.getenv("CR_ATREST_KEY")
    if not key:
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
