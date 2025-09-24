"""Database helpers for the legal corpus."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(dsn: str | None = None, echo: bool = False) -> Engine:
    """Return SQLAlchemy engine.

    DSN is read from ``LEGAL_CORPUS_DSN`` environment variable when not
    provided. Defaults to SQLite database under ``var/``.
    """

    if dsn is None:
        dsn = os.getenv("LEGAL_CORPUS_DSN", "sqlite:///var/corpus.db")
    if dsn.startswith("sqlite:///"):
        path_str = dsn.replace("sqlite:///", "", 1)
        db_path = Path(path_str)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(dsn, echo=echo, future=True)


# Session factory; sessions are normally bound in tests to a specific engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)


from .models import Base  # imported late to avoid circular import

try:  # ensure retrieval models are registered
    from contract_review_app.retrieval.models import CorpusChunk  # noqa: F401
except Exception:  # pragma: no cover
    CorpusChunk = None


DDL_LEGAL_CORPUS = """
CREATE TABLE IF NOT EXISTS legal_corpus (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  act_code TEXT NOT NULL,
  act_title TEXT NOT NULL,
  section_code TEXT NOT NULL,
  section_title TEXT NOT NULL,
  version TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  url TEXT,
  rights TEXT NOT NULL,
  lang TEXT,
  script TEXT,
  text TEXT NOT NULL,
  checksum TEXT NOT NULL,
  latest BOOLEAN DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(engine: Engine | None = None, create_all: bool = True) -> None:
    """Initialise the database schema."""

    e = engine or get_engine()
    if create_all:
        Base.metadata.create_all(e)

    dialect = e.dialect.name
    if dialect == "sqlite":
        sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique "
            "ON corpus_docs (jurisdiction, act_code, section_code) "
            "WHERE latest = 1;"
        )
        _exec_ddl(e, sql)
        fts_sql = (
            "CREATE VIRTUAL TABLE IF NOT EXISTS corpus_chunks_fts "
            "USING fts5(text, jurisdiction, source, act_code, section_code, version, "
            "content='corpus_chunks', content_rowid='id');"
        )
        _exec_ddl(e, fts_sql)
        triggers = [
            "CREATE TRIGGER IF NOT EXISTS corpus_chunks_ai AFTER INSERT ON corpus_chunks BEGIN "
            "INSERT INTO corpus_chunks_fts(rowid, text, jurisdiction, source, act_code, section_code, version) "
            "VALUES (new.id, new.text, new.jurisdiction, new.source, new.act_code, new.section_code, new.version); END;",
            "CREATE TRIGGER IF NOT EXISTS corpus_chunks_au AFTER UPDATE ON corpus_chunks BEGIN "
            "UPDATE corpus_chunks_fts SET text=new.text, jurisdiction=new.jurisdiction, source=new.source, act_code=new.act_code, section_code=new.section_code, version=new.version WHERE rowid=new.id; END;",
            "CREATE TRIGGER IF NOT EXISTS corpus_chunks_ad AFTER DELETE ON corpus_chunks BEGIN "
            "DELETE FROM corpus_chunks_fts WHERE rowid=old.id; END;",
        ]
        for t in triggers:
            _exec_ddl(e, t)
    elif dialect == "postgresql":
        sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique "
            "ON corpus_docs (jurisdiction, act_code, section_code) "
            "WHERE latest = TRUE;"
        )
        _exec_ddl(e, sql)

    _exec_ddl(e, DDL_LEGAL_CORPUS)
    _exec_ddl(
        e,
        """
          CREATE UNIQUE INDEX IF NOT EXISTS uq_doc_version
          ON legal_corpus (source, jurisdiction, act_code, section_code, version)
        """,
    )
    try:
        _exec_ddl(
            e,
            """
              CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique
              ON legal_corpus (source, jurisdiction, act_code, section_code)
              WHERE latest = TRUE
            """,
        )
    except Exception:
        pass


def _exec_ddl(engine: Engine, sql: str) -> None:
    """Execute raw DDL statement."""
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
