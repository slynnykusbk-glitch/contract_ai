export async function postJson(path: string, body: unknown) {
  const apiBase = (document.getElementById('backendUrl') as HTMLInputElement)?.value || 'https://localhost:9443';
  // headers are persisted in localStorage keys `api_key` and `schema_version`
  const apiKey = localStorage.getItem('api_key') || '';
  const schema = localStorage.getItem('schema_version') || '';

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) headers['x-api-key'] = apiKey;
  if (schema) headers['x-schema-version'] = schema;

  const res = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  });
  return res;
}
