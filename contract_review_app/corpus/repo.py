"""Repository layer for the legal corpus."""

from __future__ import annotations

from typing import TypedDict, Optional, Dict, List

from sqlalchemy import select, update, delete, or_, func
from sqlalchemy.orm import Session

from .models import CorpusDoc
from .normalizer import normalize_text, utc_iso, checksum_for


class CorpusRecord(TypedDict, total=False):
    source: str
    jurisdiction: str
    act_code: str
    act_title: str
    section_code: str
    section_title: str
    version: str
    updated_at: str
    url: Optional[str]
    rights: str
    lang: Optional[str]
    script: Optional[str]
    text: str


class CorpusRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # upsert operation with normalisation and checksum
    def upsert(self, dto: CorpusRecord) -> CorpusDoc:
        normalized_text = normalize_text(dto["text"])
        updated_at = utc_iso(dto["updated_at"])
        checksum = checksum_for(
            dto["jurisdiction"],
            dto["act_code"],
            dto["section_code"],
            dto["version"],
            normalized_text,
        )

        stmt = select(CorpusDoc).where(
            CorpusDoc.jurisdiction == dto["jurisdiction"],
            CorpusDoc.act_code == dto["act_code"],
            CorpusDoc.section_code == dto["section_code"],
            CorpusDoc.version == dto["version"],
        )

        if self.session.get_transaction() is not None:
            self.session.rollback()

        with self.session.begin():
            existing = self.session.execute(stmt).scalar_one_or_none()
            if existing and existing.checksum == checksum:
                doc = existing
            elif existing:
                existing.source = dto["source"]
                existing.act_title = dto["act_title"]
                existing.section_title = dto["section_title"]
                existing.updated_at = updated_at
                existing.url = dto.get("url")
                existing.rights = dto["rights"]
                existing.lang = dto.get("lang")
                existing.script = dto.get("script")
                existing.text = normalized_text
                existing.checksum = checksum
                doc = existing
            else:
                doc = CorpusDoc(
                    source=dto["source"],
                    jurisdiction=dto["jurisdiction"],
                    act_code=dto["act_code"],
                    act_title=dto["act_title"],
                    section_code=dto["section_code"],
                    section_title=dto["section_title"],
                    version=dto["version"],
                    updated_at=updated_at,
                    url=dto.get("url"),
                    rights=dto["rights"],
                    lang=dto.get("lang"),
                    script=dto.get("script"),
                    text=normalized_text,
                    checksum=checksum,
                    latest=False,
                )
                self.session.add(doc)
            self.session.flush()

            max_version = self.session.execute(
                select(func.max(CorpusDoc.version)).where(
                    CorpusDoc.jurisdiction == dto["jurisdiction"],
                    CorpusDoc.act_code == dto["act_code"],
                    CorpusDoc.section_code == dto["section_code"],
                )
            ).scalar_one()

            self.session.execute(
                update(CorpusDoc)
                .where(
                    CorpusDoc.jurisdiction == dto["jurisdiction"],
                    CorpusDoc.act_code == dto["act_code"],
                    CorpusDoc.section_code == dto["section_code"],
                )
                .values(latest=False)
            )
            self.session.execute(
                update(CorpusDoc)
                .where(
                    CorpusDoc.jurisdiction == dto["jurisdiction"],
                    CorpusDoc.act_code == dto["act_code"],
                    CorpusDoc.section_code == dto["section_code"],
                    CorpusDoc.version == max_version,
                )
                .values(latest=True)
            )
            self.session.refresh(doc)
        doc.updated_at = utc_iso(doc.updated_at)
        return doc

    def get_by_key(
        self, jurisdiction: str, act_code: str, section_code: str, version: str
    ) -> Optional[CorpusDoc]:
        stmt = select(CorpusDoc).where(
            CorpusDoc.jurisdiction == jurisdiction,
            CorpusDoc.act_code == act_code,
            CorpusDoc.section_code == section_code,
            CorpusDoc.version == version,
        )
        result = self.session.execute(stmt).scalar_one_or_none()
        self.session.commit()
        return result

    def list_latest(self, filters: Optional[Dict[str, str]] = None) -> List[CorpusDoc]:
        stmt = select(CorpusDoc).where(CorpusDoc.latest.is_(True))
        if filters:
            if source := filters.get("source"):
                stmt = stmt.where(CorpusDoc.source == source)
            if jurisdiction := filters.get("jurisdiction"):
                stmt = stmt.where(CorpusDoc.jurisdiction == jurisdiction)
            if act_code := filters.get("act_code"):
                stmt = stmt.where(CorpusDoc.act_code == act_code)
        res = self.session.execute(stmt).scalars().all()
        self.session.commit()
        return res

    def group_latest_count(
        self, jurisdiction: str, act_code: str, section_code: str
    ) -> int:
        stmt = select(func.count()).where(
            CorpusDoc.jurisdiction == jurisdiction,
            CorpusDoc.act_code == act_code,
            CorpusDoc.section_code == section_code,
            CorpusDoc.latest.is_(True),
        )
        count = self.session.execute(stmt).scalar_one()
        self.session.commit()
        return int(count)

    def find(
        self,
        jurisdiction: Optional[str] = None,
        act_code: Optional[str] = None,
        section_code: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[CorpusDoc]:
        stmt = select(CorpusDoc)
        if jurisdiction:
            stmt = stmt.where(CorpusDoc.jurisdiction == jurisdiction)
        if act_code:
            stmt = stmt.where(CorpusDoc.act_code == act_code)
        if section_code:
            stmt = stmt.where(CorpusDoc.section_code == section_code)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(CorpusDoc.text).like(like),
                    func.lower(CorpusDoc.section_title).like(like),
                    func.lower(CorpusDoc.act_title).like(like),
                )
            )
        res = self.session.execute(stmt).scalars().all()
        self.session.commit()
        return res

    def delete_all(self) -> None:
        if self.session.get_transaction() is not None:
            self.session.rollback()
        with self.session.begin():
            self.session.execute(delete(CorpusDoc))


# Backwards-compatible alias
Repo = CorpusRepository
