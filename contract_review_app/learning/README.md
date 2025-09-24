# Learning (local, opt-in)

Purpose: local, deterministic template re-ranking based on user actions (Apply/Reject). No raw contract text ever stored. Append-only JSONL with per-machine salt and HMAC to ensure privacy and integrity.

## Opt-in / Opt-out

- Default: OFF in UI (panel toggle). Backend also checks env:
  - `LEARNING_ENABLED=0|false|off` => Learning API rejects writes (HTTP 403).
  - `LEARNING_ENABLED=1` (or unset) => Learning API accepts events.
- You can disable at any time without impacting the rule engine.

## What we log (JSONL event)

Only metadata and salted hashes, never raw clause or document text.

Required fields (ASCII-only):
- `schema_ver`, `event_id`, `event_key` (dedup hash), `ts`
- `user` (e.g., "local"), `user_role` ("buyer"|"seller"|"neutral")
- `doc_id` (sha256(text|salt)), `clause_id`, `clause_type`, `contract_type`
- `mode` ("friendly"|"standard"|"strict"), `action` ("applied"|"rejected"|"accepted_all"|"rejected_all")
- `template_id`, optional `suggestion_id`
- `span` {start,length}
- `context` {jurisdiction, language, policy_pack, risk_ord, severity_max}
- `proposed_text_hash` (sha256(text|salt))
- `verdict_snapshot` {status_from,status_to,risk_ord_from,risk_ord_to,score_delta}
- `ui_latency_ms`, `client` {cid, app_build, panel_build}
- `hmac` (hex signature over the JSON without `hmac`, using local key)

Full example in the spec we used during design.

## What we NEVER log

- No raw contract text, no party names, no monetary amounts, no emails, no addresses.

## Storage layout
