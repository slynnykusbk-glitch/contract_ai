from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from contract_review_app.security.secure_store import secure_write


def audit(
    event: str, user: Optional[str], doc_hash: Optional[str], details: Dict[str, Any]
) -> None:
    """Write audit entry as encrypted JSON line."""

    os.makedirs("var", exist_ok=True)
    record: Dict[str, Any] = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "user": user,
        "hash_doc": (
            hashlib.blake2b(
                (doc_hash or "").encode("utf-8"), digest_size=16
            ).hexdigest()
            if doc_hash
            else None
        ),
        "pii_present": bool(details.pop("pii_present", False)),
        "redaction_policy": "auto",
    }
    if details:
        record.update(details)
    try:
        secure_write(
            os.path.join("var", "audit.log"),
            json.dumps(record, sort_keys=True),
            append=True,
        )
    except Exception as exc:  # pragma: no cover - rare
        logging.warning("failed to write audit log: %s", exc)


__all__ = ["audit"]
