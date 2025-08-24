# Goals
- Panel (Word add-in UI) runs at https://127.0.0.1:3000
- Backend FastAPI runs at https://127.0.0.1:9443
- GET /health -> JSON with rules_count > 0
- POST /api/analyze(sample) -> findings.length >= 1
- Fix QA Recheck: 'Clause' has no attribute 'get'
- LLM draft: fallback to stub when no API keys
