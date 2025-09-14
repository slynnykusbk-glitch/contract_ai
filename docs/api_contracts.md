# API contracts: /api/analyze

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
