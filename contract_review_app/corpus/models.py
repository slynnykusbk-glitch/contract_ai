from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class LegalCorpus(Base):
    __tablename__ = "legal_corpus"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    act_code = Column(String, nullable=False)
    act_title = Column(String, nullable=False)
    section_code = Column(String, nullable=False)
    section_title = Column(String, nullable=False)
    version = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    url = Column(String)
    rights = Column(String, nullable=False)
    lang = Column(String)
    script = Column(String)
    text = Column(Text, nullable=False)
    checksum = Column(String, nullable=False)
    latest = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
