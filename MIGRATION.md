# B9-S2
- `/api/analyze` envelope now includes `schema_version`, `results.summary` and returns uppercase `status`.

# B9-S6 — Trace & Report Export

- `GET /api/trace/{cid}` returns a structured payload with keys `cid`, `created_at`,
  `input`, `analysis`, `meta` and `x_schema_version`.
- Export analysis reports via `GET /api/report/{cid}.html` (always on) and
  `GET /api/report/{cid}.pdf` (returns 501 if PDF backend missing).
- Use the `x-cid` response header from `/api/analyze` as the identifier.
- Trace middleware now persists up to 200 entries (configurable via `TRACE_MAX`)
  and accepts CID values matching ``^[A-Za-z0-9\-:]{3,64}$``.

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

# Block B6-3 — Retrieval config & vector cache

Configuration lives in `config/retrieval.yaml`:

```yaml
vector:
  backend: inmemory
  embedding_dim: 128
  embedding_version: emb-dev-1
  cache_dir: .cache/retrieval
fusion:
  method: rrf
  weights:
    vector: 0.6
    bm25: 0.4
  rrf_k: 60
bm25:
  top: 10
```

`fusion.method` controls how BM25 and vector results are combined: "rrf" for
reciprocal rank fusion (default) or "weighted" for weighted hybrid using the
specified `weights`.

Environment overrides:

```
RETRIEVAL_CONFIG            # path to YAML
RETRIEVAL_EMBEDDING_DIM     # int
RETRIEVAL_EMBEDDING_VERSION # string
RETRIEVAL_CACHE_DIR         # cache location
RETRIEVAL_RRF_K             # int
RETRIEVAL_FUSION_METHOD     # rrf|weighted
RETRIEVAL_WEIGHT_VECTOR     # float
RETRIEVAL_WEIGHT_BM25       # float
RETRIEVAL_BM25_TOP          # int
```

Build vector cache:

```bash
make retrieval-build
```

# Block B6-5 — Retrieval evaluation

Run offline evaluation on the demo corpus. Hybrid search should reach at least
80% recall@5 and MRR above 0.6.

```bash
python -m contract_review_app.corpus.ingest --dir data/corpus_demo
python -m contract_review_app.retrieval.indexer
python -m contract_review_app.retrieval.eval --golden data/retrieval_golden.yaml --method hybrid --k 5
```

Exit code is zero when both recall and MRR thresholds for the selected method
are met (0.8/0.6 for hybrid, 0.6/0.5 for bm25/vector).

# Testing

tests reset analyze idempotency cache per test via conftest.py

# Block B6-6 — Highlight snippets and offsets

Search responses now expose additional context for each chunk:

* `snippet` – a short window around the first query token match,
* `span` – exact `start`/`end` offsets in the source document.

These rely on the offset map stored in `corpus_chunks` and help clients
highlight matches in the original text.

# Block B8-S1 — Unified API error format

## Summary

All endpoints now return a standard ProblemDetail JSON body for 4xx/5xx errors.

* Added `ProblemDetail` schema and global exception handlers.
* FastAPI default error responses: 400/401/403/404/422/429/500.
* OpenAPI components include `ProblemDetail`; key routes expose it explicitly.

## How to verify

```bash
curl -X POST localhost:8000/api/analyze -d '{"text":123}' -H 'Content-Type: application/json'
curl -X POST localhost:8000/api/gpt/draft -d '{}' -H 'Content-Type: application/json'
```

Both calls return `{"type":"/errors/general","title":...,"status":422}`.

# Block B8-S3 — Standard API headers

## Summary

Every API response now includes three standard headers:

* `x-schema-version` – current schema version (`1.3`).
* `x-latency-ms` – request processing time in milliseconds.
* `x-cid` – deterministic SHA256 hash of the canonical request (`path + sorted(query) + JSON body`).

## How to verify

```bash
curl -i -X POST localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello"}'
```

Repeated calls with the same payload yield identical `x-cid`, while changing the body alters the hash. The headers are also present on error responses.

Trace middleware теперь получает те же `x-cid`/`x-latency-ms`, что и клиент; порядок middleware фиксирован: trace → headers → endpoint → headers → trace.

# Block B8-S4 — Timeouts, 429, Pagination

## Summary

* Added global request timeout and rate limiting.
* List endpoints now support pagination.
* OpenAPI documents new responses (429/504) and paging parameters.

## Environment variables

```bash
CONTRACTAI_API_TIMEOUT_S   # default 30
CONTRACTAI_RATE_PER_MIN    # default 60
CONTRACTAI_PAGE_SIZE       # default 10
CONTRACTAI_MAX_PAGE_SIZE   # default 50
```

## Examples

Timeout (504):

```bash
curl -i /api/analyze -d '{"text":"slow"}' -H 'Content-Type: application/json'
```

Too many requests (429):

```bash
curl -i -X POST /api/analyze -d '{"text":"hi"}' -H 'Content-Type: application/json'
```

Pagination:

```bash
curl -X POST '/api/corpus/search?page=2&page_size=5' -d '{"q":"data"}' -H 'Content-Type: application/json'
```

# Block B8-S5 — LLM providers

By default the application uses a mock LLM provider (`LLM_PROVIDER=mock`).

For Azure integration set the following environment variables:

* `AZURE_OPENAI_ENDPOINT`
* `AZURE_OPENAI_DEPLOYMENT`
* `AZURE_OPENAI_API_KEY`
* optional `AZURE_OPENAI_API_VERSION`

The `/api/gpt-draft` endpoint resolves the provider lazily via `provider_from_env()`.

# Block B8-S6 — `/api/analyze` usage

Example request:

```bash
curl -s -X POST localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world"}'
```

Example response:

```json
{
  "status": "ok",
  "analysis": {"findings": []},
  "meta": {"provider": "mock", "model": "mock"}
}
```

## ENV matrix

The Azure client now reads configuration from multiple environment variables. The
following matrix shows the accepted names:

| Setting   | Variables (priority order)                                  |
|-----------|-------------------------------------------------------------|
| endpoint  | `AZURE_OPENAI_ENDPOINT`                                     |
| version   | `AZURE_OPENAI_API_VERSION`                                  |
| deployment| `AZURE_OPENAI_DEPLOYMENT`                                   |
| API key   | `AZURE_OPENAI_KEY` → `AZURE_OPENAI_API_KEY` → `OPENAI_API_KEY` |

### curl examples

```bash
curl -s -X POST localhost:8000/api/gpt-draft \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Example clause.","profile":"smart"}'

curl -s -X POST localhost:8000/api/suggest_edits \
  -H 'Content-Type: application/json' \
  -d '{"text":"Confidential info"}'

curl -s -X POST localhost:8000/api/qa-recheck \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello"}'
```
