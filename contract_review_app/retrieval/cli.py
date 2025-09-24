from __future__ import annotations

import argparse
import json

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from .config import load_config
from .cache import ensure_vector_cache
from .embedder import HashingEmbedder


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["build"])
    args = p.parse_args()
    if args.command == "build":
        cfg = load_config()
        engine = get_engine()
        init_db(engine)
        SessionLocal.configure(bind=engine)
        with SessionLocal() as session:
            embedder = HashingEmbedder(cfg["vector"]["embedding_dim"])
            vecs, ids, _, from_cache = ensure_vector_cache(
                session,
                embedder=embedder,
                cache_dir=cfg["vector"]["cache_dir"],
                emb_ver=cfg["vector"]["embedding_version"],
            )
        out = {
            "built": not from_cache,
            "from_cache": from_cache,
            "count": int(len(ids)),
        }
        print(json.dumps(out))


if __name__ == "__main__":
    main()
