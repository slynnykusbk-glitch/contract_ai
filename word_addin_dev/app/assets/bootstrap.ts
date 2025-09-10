export async function bootstrapHeaders() {
  // DEV ONLY: auto-populate schema and API key
  if (!localStorage.getItem('schema_version')) {
    try {
      const h = await fetch('/health').then(r => r.json());
      if (h && h.schema) {
        localStorage.setItem('schema_version', String(h.schema));
      }
    } catch {}
  }
  if (!localStorage.getItem('api_key')) {
    const k = (window as any).__DEV_DEFAULT_API_KEY__;
    if (k) localStorage.setItem('api_key', k);
  }
}
// immediately bootstrap on import
bootstrapHeaders();
