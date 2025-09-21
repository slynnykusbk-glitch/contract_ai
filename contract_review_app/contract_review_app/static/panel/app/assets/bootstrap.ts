import { checkHealth } from './health.ts';

export async function bootstrapHeaders() {
  // DEV ONLY: auto-populate schema and API key
  if (!localStorage.getItem('schema_version')) {
    try {
      const { json } = await checkHealth();
      if (json && json.schema) {
        localStorage.setItem('schema_version', String(json.schema));
      }
    } catch {}
  }
  if (!localStorage.getItem('api_key')) {
    const k = (window as any).__DEV_DEFAULT_API_KEY__;
    if (k) localStorage.setItem('api_key', k);
  }
  localStorage.setItem('cai.force.comments', '1');
}
// immediately bootstrap on import
bootstrapHeaders();
