from __future__ import annotations

from typing import Iterable, List
from sqlalchemy import or_, func

from .models import LegalCorpus


class Repo:
    def __init__(self, session):
        self.session = session

    def upsert(self, dto: dict) -> LegalCorpus:
        key_filter = {
            "jurisdiction": dto["jurisdiction"],
            "act_code": dto["act_code"],
            "section_code": dto["section_code"],
            "version": dto["version"],
            "checksum": dto["checksum"],
        }
        existing = (
            self.session.query(LegalCorpus)
            .filter_by(**key_filter)
            .one_or_none()
        )
        if existing:
            return existing

        # mark previous latest as false
        self.session.query(LegalCorpus).filter_by(
            jurisdiction=dto["jurisdiction"],
            act_code=dto["act_code"],
            section_code=dto["section_code"],
            latest=True,
        ).update({"latest": False})

        obj = LegalCorpus(**dto, latest=True)
        self.session.add(obj)
        self.session.commit()
        return obj

    def list_latest(self) -> List[LegalCorpus]:
        return (
            self.session.query(LegalCorpus)
            .filter_by(latest=True)
            .all()
        )

    def find(
        self,
        *,
        jurisdiction: str | None = None,
        act_code: str | None = None,
        q: str | None = None,
    ) -> List[LegalCorpus]:
        query = self.session.query(LegalCorpus).filter_by(latest=True)
        if jurisdiction:
            query = query.filter(LegalCorpus.jurisdiction == jurisdiction)
        if act_code:
            query = query.filter(LegalCorpus.act_code == act_code)
        if q:
            pattern = f"%{q.lower()}%"
            query = query.filter(
                or_(
                    func.lower(LegalCorpus.text).like(pattern),
                    func.lower(LegalCorpus.act_title).like(pattern),
                    func.lower(LegalCorpus.section_title).like(pattern),
                )
            )
        return query.all()
