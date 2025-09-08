import os
import time
from importlib import reload

from contract_review_app.tools import purge_retention


def test_retention_purge(tmp_path, monkeypatch):
    var = tmp_path / "var"
    var.mkdir()
    old = var / "old.log"
    old.write_text("x")
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))
    monkeypatch.setenv("CR_RETENTION_DAYS", "30")
    reload(purge_retention)
    purge_retention.VAR_PATH = var
    removed = purge_retention.purge(dry_run=False)
    assert old not in var.iterdir()
    assert old in removed
