from __future__ import annotations

import json
import os
from pathlib import Path

from .db import get_engine, init_db, SessionLocal


def corpus_summary(session) -> dict:
    from sqlalchemy import func
    from .models import CorpusDoc

    rows = (
        session.query(
            CorpusDoc.jurisdiction,
            CorpusDoc.act_code,
            func.count().label("sections"),
        )
        .filter(CorpusDoc.latest)
        .group_by(CorpusDoc.jurisdiction, CorpusDoc.act_code)
        .all()
    )
    return {f"{j}/{a}": s for j, a, s in rows}


def main() -> dict:
    dsn = os.getenv("LEGAL_CORPUS_DSN")
    if dsn is None:
        local = Path(".local")
        local.mkdir(exist_ok=True)
        dsn = f"sqlite:///{(local / 'corpus.db').resolve()}"

    engine = get_engine(dsn)
    init_db(engine, create_all=False)
    session = SessionLocal(bind=engine)
    summary = corpus_summary(session)
    session.close()

    text = json.dumps(summary, indent=2, sort_keys=True)
    print(text)
    Path("corpus_demo_report.json").write_text(text, encoding="utf-8")
    return summary


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
