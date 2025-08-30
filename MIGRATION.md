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
