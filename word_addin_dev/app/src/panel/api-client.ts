export async function postJson(path: string, body: unknown) {
  const apiBase = (document.getElementById('backendUrl') as HTMLInputElement)?.value || 'https://localhost:9443';
  // headers are persisted in localStorage keys `api_key` and `schemaVersion`
  const apiKey = localStorage.getItem('api_key') || '';
  const schema = localStorage.getItem('schemaVersion') || '';

  if (!apiKey || !schema) throw new Error('MISSING_HEADERS');

  const res = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'x-schema-version': schema
    },
    body: JSON.stringify(body)
  });
  return res;
}
