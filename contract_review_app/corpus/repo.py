from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select, update, func

from .db import LegalCorpus


_TRANSLATION = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u00a0": " ",
    }
)


def normalize_text(text: str) -> str:
    text = text.translate(_TRANSLATION)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CorpusDTO:
    jurisdiction: str
    act_code: str
    section_code: str
    version: str
    text: str


class Repo:
    def __init__(self, Session):
        self.Session = Session

    def upsert(self, dto: CorpusDTO) -> LegalCorpus:
        with self.Session() as session:
            with session.begin():
                norm = normalize_text(dto.text)
                ch = compute_checksum(norm)
                stmt = select(LegalCorpus).where(
                    LegalCorpus.jurisdiction == dto.jurisdiction,
                    LegalCorpus.act_code == dto.act_code,
                    LegalCorpus.section_code == dto.section_code,
                    LegalCorpus.version == dto.version,
                )
                existing = session.execute(stmt).scalar_one_or_none()
                if existing:
                    if existing.checksum != ch:
                        existing.text = dto.text
                        existing.checksum = ch
                else:
                    existing = LegalCorpus(
                        jurisdiction=dto.jurisdiction,
                        act_code=dto.act_code,
                        section_code=dto.section_code,
                        version=dto.version,
                        text=dto.text,
                        checksum=ch,
                        latest=False,
                    )
                    session.add(existing)

                session.execute(
                    update(LegalCorpus)
                    .where(
                        LegalCorpus.jurisdiction == dto.jurisdiction,
                        LegalCorpus.act_code == dto.act_code,
                        LegalCorpus.section_code == dto.section_code,
                    )
                    .values(latest=False)
                )
                max_row = session.execute(
                    select(LegalCorpus)
                    .where(
                        LegalCorpus.jurisdiction == dto.jurisdiction,
                        LegalCorpus.act_code == dto.act_code,
                        LegalCorpus.section_code == dto.section_code,
                    )
                    .order_by(LegalCorpus.version.desc())
                    .limit(1)
                ).scalar_one()
                max_row.latest = True
                session.flush()
                session.expunge(existing)
                return existing

    def group_latest_count(
        self, jurisdiction: str, act_code: str, section_code: str
    ) -> int:
        with self.Session() as session:
            return session.scalar(
                select(func.count()).where(
                    LegalCorpus.jurisdiction == jurisdiction,
                    LegalCorpus.act_code == act_code,
                    LegalCorpus.section_code == section_code,
                    LegalCorpus.latest.is_(True),
                )
            )

    def list_latest(self, filters: Optional[dict] = None) -> Iterable[LegalCorpus]:
        filters = filters or {}
        with self.Session() as session:
            stmt = select(LegalCorpus).where(LegalCorpus.latest.is_(True))
            if "jurisdiction" in filters:
                stmt = stmt.where(LegalCorpus.jurisdiction == filters["jurisdiction"])
            if "act_code" in filters:
                stmt = stmt.where(LegalCorpus.act_code == filters["act_code"])
            if "section_code" in filters:
                stmt = stmt.where(LegalCorpus.section_code == filters["section_code"])
            return session.execute(stmt).scalars().all()
