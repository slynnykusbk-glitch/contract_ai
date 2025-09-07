# Contract AI

## LLM config

Environment variables controlling the language model provider:

```
AI_PROVIDER=mock|openai|azure|anthropic|openrouter
OPENAI_API_KEY=
OPENAI_BASE=https://api.openai.com/v1
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
ANTHROPIC_API_KEY=
ANTHROPIC_BASE=https://api.anthropic.com/v1
OPENROUTER_API_KEY=
OPENROUTER_BASE=https://openrouter.ai/api/v1
MODEL_DRAFT=
MODEL_SUGGEST=
MODEL_QA=
LLM_TIMEOUT_S=30
LLM_MAX_TOKENS=800
LLM_TEMPERATURE=0.2
```

Defaults use a deterministic mock model so the application works without keys. Set the relevant variables for live providers.

## Word Add-in

After running an analysis the task pane displays the current CID. You can open
`/api/trace/{cid}` via the **View Trace** button or export the analysis using
**Export HTML/PDF**. The **Replay last** button re-sends the previous input to
`/api/analyze`.

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
