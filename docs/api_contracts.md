# API contracts: /api/analyze

Frontend sends a flat JSON body. The server tolerates the legacy wrapper `{ "payload": { ... } }` only for backward compatibility.

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
