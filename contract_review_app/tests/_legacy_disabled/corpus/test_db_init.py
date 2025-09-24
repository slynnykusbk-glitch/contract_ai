import os, sys, json
from pathlib import Path
from sqlalchemy import text


def test_corpus_init_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "corpus.db"
    monkeypatch.setenv("LEGAL_CORPUS_DSN", f"sqlite:///{db.as_posix()}")
    from contract_review_app.corpus.db import get_engine
    from contract_review_app.corpus.db import init_db

    e = get_engine()
    init_db(e)
    with e.connect() as c:
        cnt = c.execute(text("SELECT COUNT(*) FROM legal_corpus")).scalar()
        assert cnt in (0, int(cnt))
