"""Legal corpus data layer."""

from .db import get_engine, SessionLocal, init_db
from .repo import CorpusRepository

__all__ = [
    "get_engine",
    "SessionLocal",
    "init_db",
    "CorpusRepository",
]
