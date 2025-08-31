from __future__ import annotations

import re

from sqlalchemy.orm import Session


class BM25Search:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        source: str | None = None,
        act_code: str | None = None,
        section_code: str | None = None,
        top: int = 10,
    ):
        terms = re.findall(r"\w+", query.lower())
        if not terms:
            return []

        def _prefix(t: str) -> str:
            for suf in ("ing", "ed", "es", "s"):
                if t.endswith(suf) and len(t) - len(suf) >= 3:
                    t = t[: -len(suf)]
                    break
            return f"{t}*"

        q = " OR ".join(_prefix(t) for t in terms)
        sql = (
            "SELECT c.id, c.corpus_id, c.start, c.end, c.jurisdiction, c.source, c.act_code, c.section_code, c.version, c.lang, c.text, bm25(corpus_chunks_fts) AS score "
            "FROM corpus_chunks_fts JOIN corpus_chunks c ON c.id = corpus_chunks_fts.rowid "
            "WHERE corpus_chunks_fts MATCH :q"
        )
        params: dict[str, object] = {"q": q, "top": top}
        if jurisdiction:
            sql += " AND c.jurisdiction = :jurisdiction"
            params["jurisdiction"] = jurisdiction
        if source:
            sql += " AND c.source = :source"
            params["source"] = source
        if act_code:
            sql += " AND c.act_code = :act_code"
            params["act_code"] = act_code
        if section_code:
            sql += " AND c.section_code = :section_code"
            params["section_code"] = section_code
        sql += " ORDER BY score LIMIT :top"
        conn = self.session.connection()
        res = conn.exec_driver_sql(sql, params)
        return [dict(r) for r in res.mappings()]
