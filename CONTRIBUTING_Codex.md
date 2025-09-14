# Contributing to Contract AI

## Golden Rules
- Modify existing modules instead of creating copies. Do **not** add files like `*_copy.py`.
- Public APIs (endpoints and DTOs) must keep their names and shapes.
- Client implementations must honour the `BaseClient` interface and provide:
  - `draft(prompt, max_tokens, temperature, timeout)`
  - `suggest_edits(prompt, timeout)`
  - `qa_recheck(prompt, timeout)`
  Each method must return the expected dataclass (`DraftResult`, `SuggestResult`, `QAResult`).
- Avoid committing merge markers (`<<<<<<<`, `=======`, `>>>>>>>`) or stray lines such as `codex/...`.

## Adding a Provider Client
- Place new clients under `contract_review_app/gpt/clients/*_client.py`.
- Implement all `BaseClient` methods and return the correct dataclasses.
- Keep imports relative within the `contract_review_app` package.

## LLMService Expectations
- `LLMService.draft()` may delegate to `client.generate_draft()`, but the client **must** also implement `draft` to satisfy `BaseClient`.
- When extending `LLMService`, ensure the service still calls the client's `draft`, `suggest_edits`, and `qa_recheck` methods.

## Local Development
1. Run tests:
   ```powershell
   .\run_tests.ps1
   ```
2. Run the interface doctor:
   ```bash
   python tools/doctor.py
   ```

## Quality Notes
- Keep files free of conflict markers and temporary strings like `codex/...`.
- Remove generated caches (`__pycache__`) before committing.
- All tests and the doctor script must succeed with `LLM_PROVIDER=mock` and without external API keys.

## API Contracts
See [docs/api_contracts.md](docs/api_contracts.md) for request/response examples, such as `/api/analyze`.
TypeScript types are generated to [word_addin_dev/app/types/api.d.ts](word_addin_dev/app/types/api.d.ts).
