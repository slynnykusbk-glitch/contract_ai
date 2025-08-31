"""Database helpers for the legal corpus."""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(dsn: str | None = None, echo: bool = False) -> Engine:
    """Return SQLAlchemy engine.

    DSN is read from ``LEGAL_CORPUS_DSN`` environment variable when not
    provided. Defaults to in-memory SQLite database.
    """

    if dsn is None:
        dsn = os.getenv("LEGAL_CORPUS_DSN", "sqlite:///:memory:")
    return create_engine(dsn, echo=echo, future=True)


# Session factory; sessions are normally bound in tests to a specific engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)


from .models import Base  # imported late to avoid circular import
try:  # ensure retrieval models are registered
    from contract_review_app.retrieval.models import CorpusChunk  # noqa: F401
except Exception:  # pragma: no cover
    CorpusChunk = None


def init_db(engine: Engine, create_all: bool = True) -> None:
    """Initialise the database schema."""

    if create_all:
        Base.metadata.create_all(engine)

    dialect = engine.dialect.name
    if dialect == "sqlite":
        sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique "
            "ON corpus_docs (jurisdiction, act_code, section_code) "
            "WHERE latest = 1;"
        )
        _exec_ddl(engine, sql)
        fts_sql = (
            "CREATE VIRTUAL TABLE IF NOT EXISTS corpus_chunks_fts "
            "USING fts5(text, jurisdiction, source, act_code, section_code, version, "
            "content='corpus_chunks', content_rowid='id');"
        )
        _exec_ddl(engine, fts_sql)
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
            _exec_ddl(engine, t)
    elif dialect == "postgresql":
        sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique "
            "ON corpus_docs (jurisdiction, act_code, section_code) "
            "WHERE latest = TRUE;"
        )
        _exec_ddl(engine, sql)


def _exec_ddl(engine: Engine, sql: str) -> None:
    """Execute raw DDL statement."""
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
