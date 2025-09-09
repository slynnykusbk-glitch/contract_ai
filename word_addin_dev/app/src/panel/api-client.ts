export async function postJson(path: string, body: unknown) {
  const apiBase = (document.getElementById('backendUrl') as HTMLInputElement)?.value || 'https://localhost:9443';
  const apiKey = localStorage.getItem('x-api-key') || '';
  const schema = localStorage.getItem('x-schema-version') || '';

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
