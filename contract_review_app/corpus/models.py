"""SQLAlchemy models for the legal corpus."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CorpusDoc(Base):
    __tablename__ = "corpus_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(8), nullable=False)
    act_code: Mapped[str] = mapped_column(String(128), nullable=False)
    act_title: Mapped[str] = mapped_column(String(256), nullable=False)
    section_code: Mapped[str] = mapped_column(String(128), nullable=False)
    section_title: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rights: Mapped[str] = mapped_column(String(128), nullable=False)
    lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    script: Mapped[str | None] = mapped_column(String(16), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    latest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "jurisdiction", "act_code", "section_code", "version", name="uq_doc_version"
        ),
        Index("ix_jur_act_sec", "jurisdiction", "act_code", "section_code"),
        Index("ix_act_title", "act_title"),
        Index("ix_section_title", "section_title"),
    )

