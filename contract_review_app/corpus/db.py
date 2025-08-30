from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class LegalCorpus(Base):
    __tablename__ = "legal_corpus"

    id = Column(Integer, primary_key=True)
    jurisdiction = Column(String, nullable=False)
    act_code = Column(String, nullable=False)
    section_code = Column(String, nullable=False)
    version = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    checksum = Column(String, nullable=False)
    latest = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "jurisdiction",
            "act_code",
            "section_code",
            "version",
            name="uq_doc_version",
        ),
    )


SessionLocal = sessionmaker()


def get_engine(dsn: str):
    return create_engine(dsn, future=True)


def _exec_ddl(engine, sql: str) -> None:
    with engine.connect() as conn:
        conn.exec_driver_sql(sql)


def init_db(engine, create_all: bool = True) -> None:
    if create_all:
        Base.metadata.create_all(engine)
    dialect = engine.dialect.name
    if dialect == "sqlite":
        ddl = """CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique
ON legal_corpus (jurisdiction, act_code, section_code)
WHERE latest = 1"""
        _exec_ddl(engine, ddl)
    elif dialect == "postgresql":
        ddl = """CREATE UNIQUE INDEX IF NOT EXISTS ux_latest_unique
ON legal_corpus (jurisdiction, act_code, section_code)
WHERE latest = TRUE"""
        _exec_ddl(engine, ddl)
