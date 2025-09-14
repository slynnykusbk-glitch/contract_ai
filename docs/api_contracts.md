# API contracts: /api/analyze

See the TypeScript types in [word_addin_dev/app/types/api.d.ts](../word_addin_dev/app/types/api.d.ts).

Frontend sends a flat JSON body.

Older deployments wrapped the payload inside a `{ "payload": { ... } }` object, but this wrapper is no longer supported. Requests using the wrapper will be rejected with a validation error.

## Request

```http
POST /api/analyze
Content-Type: application/json

{
  "text": "Hello"
}
```

## Response

```json
{
  "status": "OK",
  "analysis": {},
  "schema_version": "1.4"
}
```

---

# API contracts: /api/gpt-draft

Frontend sends a flat JSON body. Aliases `text` and `clause` are accepted.

## Request

```http
POST /api/gpt-draft
Content-Type: application/json

{
  "text": "Hello"
}
```

## Response

```json
{
  "status": "ok",
  "proposed_text": "...",
  "schema_version": "1.4"
}
```
