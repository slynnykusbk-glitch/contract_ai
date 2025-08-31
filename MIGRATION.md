# Block B5 — Legal Corpus & Metadata

## Schema

```sql
CREATE TABLE legal_corpus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    act_code TEXT NOT NULL,
    act_title TEXT NOT NULL,
    section_code TEXT NOT NULL,
    section_title TEXT NOT NULL,
    version TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    url TEXT,
    rights TEXT NOT NULL,
    lang TEXT,
    script TEXT,
    text TEXT NOT NULL,
    checksum TEXT NOT NULL,
    latest BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_doc_version
ON legal_corpus (jurisdiction, act_code, section_code, version);

CREATE UNIQUE INDEX ux_latest_unique
ON legal_corpus (jurisdiction, act_code, section_code)
WHERE latest = TRUE;
```

## Usage

Dev/CI: SQLite (sqlite:///.local/corpus.db)

Prod: PostgreSQL (postgresql+psycopg://...)

Run demo ingest:

```bash
make corpus-demo
```

Run tests:

```bash
make corpus-test
```

# Block B6-1 — Retrieval baseline (FTS5)

## Schema

```sql
CREATE TABLE corpus_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus_id INTEGER NOT NULL,
    jurisdiction TEXT NOT NULL,
    source TEXT NOT NULL,
    act_code TEXT NOT NULL,
    section_code TEXT NOT NULL,
    version TEXT NOT NULL,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    lang TEXT,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    checksum TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE corpus_chunks_fts USING fts5(
    text, jurisdiction, source, act_code, section_code, version,
    content='corpus_chunks', content_rowid='id'
);
```

## How to run

Rebuild local index and run BM25 search:

```bash
python -m contract_review_app.retrieval.indexer
python -m contract_review_app.retrieval.search # library usage
```

API smoke:

```bash
uvicorn contract_review_app.api.corpus_search:router
```
