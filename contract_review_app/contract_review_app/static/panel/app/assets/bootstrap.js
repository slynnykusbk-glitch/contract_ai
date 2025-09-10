export async function bootstrapHeaders() {
  // DEV ONLY: auto-populate schema and API key
  if (!localStorage.getItem('schemaVersion')) {
    try {
      const h = await fetch('/health').then(r => r.json());
      if (h && h.schema) {
        localStorage.setItem('schemaVersion', String(h.schema));
      }
    } catch {}
  }
  if (!localStorage.getItem('api_key')) {
    const k = window.__DEV_DEFAULT_API_KEY__;
    if (k) localStorage.setItem('api_key', k);
  }
}
bootstrapHeaders();
