from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base


SessionLocal = sessionmaker()


def get_engine(dsn: str | None = None):
    dsn = dsn or os.getenv("LEGAL_CORPUS_DSN") or "sqlite:///./.local/corpus.db"
    if dsn.startswith("sqlite:///"):
        path = dsn.replace("sqlite:///", "", 1)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    return create_engine(dsn, future=True)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    SessionLocal.configure(bind=engine)
