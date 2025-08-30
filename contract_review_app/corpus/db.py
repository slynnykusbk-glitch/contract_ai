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
