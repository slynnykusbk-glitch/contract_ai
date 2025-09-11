# Contract AI

## Installation

Install required packages and verify that **PyYAML** is available for rule pack parsing by `/api/analyze`:

```bash
pip install -r requirements.txt
python -c "import yaml"
```

## LLM config

Environment variables controlling the language model provider:

```
LLM_PROVIDER=mock|azure
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=
MODEL_DRAFT=
MODEL_SUGGEST=
MODEL_QA=
LLM_TIMEOUT_S=30
LLM_MAX_TOKENS=800
LLM_TEMPERATURE=0.2
```

Defaults use a deterministic mock model so the application works without keys. Set the relevant variables for live providers.

| Variable | Valid example | Invalid example |
| --- | --- | --- |
| `AZURE_OPENAI_API_KEY` | `0123456789abcdef0123456789ab` | `changeme` |
| `AZURE_OPENAI_ENDPOINT` | `https://eastus.api.cognitive.microsoft.com` | `http://localhost` |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o-mini` | *(empty string)* |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | *(empty string)* |
| `MODEL_DRAFT` | `gpt-4o-mini` | *(empty string → ignored)* |
| `MODEL_SUGGEST` | `gpt-4o-mini` | *(empty string → ignored)* |
| `MODEL_QA` | `gpt-4o-mini` | *(empty string → ignored)* |

## Health and dependency checks

The `/health` endpoint verifies that required rule engine dependencies are
available. It attempts to import **PyYAML** and load rule packs during
application start. If these checks fail, `/health` reports a non-OK status
so deployments can detect missing dependencies. PyYAML must be present or
`/api/analyze` will not load rule packs.

Rules whose configured document types do not match the analyzed document are
now reported with the status `doc_type_mismatch` in rule coverage data. The
UI panel surfaces this status so missing coverage is visible during checks.

## Word Add-in

Фронтенд-тесты запускаются Vitest; Jest не используется.

On Windows build and test with:

```bash
cd word_addin_dev && npm ci && npm test && npm run build
cd .. && npm run build:panel
```

After running an analysis the task pane displays the current CID. You can open
`/api/trace/{cid}` via the **View Trace** button or export the analysis using
**Export HTML/PDF**. The **Replay last** button re-sends the previous input to
`/api/analyze`.

## Panel Self-Test

The file `word_addin_dev/panel_selftest.html` provides a small web page for
checking the backend API. To run the self-test:

1. Start the backend service.
2. Open `panel_selftest.html` in a browser.
3. Enter the backend URL, your API key (`x-api-key`) and the expected schema
   version (`x-schema-version`, for example `1.4`).
4. Click **Run All** or choose individual tests.

Both headers are required for most API endpoints; requests without them will
fail.

## API examples

Sample request bodies for `/api/analyze` are included:

- `analyze_req.json` – minimal request with required fields.
- `analyze_req_doctor.json` – the same request with `mode` set to `doctor`.

Run `make openapi` to regenerate `openapi.json` in the repository root.

## Insurance Rule Checker

This repository includes a simple rule-based insurance clause checker.

### Run the checker

```bash
python cli.py check path/to/contract.txt
```

Exit code `0` means all hard requirements pass, while `2` indicates at least one hard failure.

### Run tests

```bash
pytest tests/insurance -q
```

## i18n inventory

To list any Cyrillic characters in source paths run:

```bash
rg -n --pcre2 "[\p{Cyrillic}]" contract_review_app core word_addin_dev | tee i18n_inventory.txt
```

The generated `i18n_inventory.txt` should be empty in a clean repository.

## Live test watch (improved)

Установка: pip install -r requirements-dev.txt

Запуск: .\ContractAI-Watch-Tests.local.ps1 (откроется окно ptw; редактируешь код — тесты идут автоматически)

Быстрый режим (по желанию): .\tools\watch_backend_tests.ps1 -Fast (pytest -f loop-on-fail)
