export type HeadersMap = Record<string, string>;
const LS = { API_KEY: 'api_key', SCHEMA: 'schema_version' } as const;

export function getStoredKey(): string {
  return localStorage.getItem(LS.API_KEY) ?? '';
}
export function getStoredSchema(): string {
  return localStorage.getItem(LS.SCHEMA) ?? '';
}
export function setStoredSchema(v: string) {
  if (v) localStorage.setItem(LS.SCHEMA, v);
}

export function ensureHeadersSet() {
  try {
    const host = (globalThis as any)?.location?.hostname ?? '';
    const isDev = host === 'localhost' || host === '127.0.0.1';
    if (isDev) {
      if (!localStorage.getItem(LS.API_KEY)) {
        localStorage.setItem(LS.API_KEY, 'local-test-key-123');
      }
      if (!localStorage.getItem(LS.SCHEMA)) {
        const envSchema =
          (globalThis as any)?.SCHEMA_VERSION ||
          (typeof process !== 'undefined' && (process as any).env?.SCHEMA_VERSION) ||
          '1.4';
        localStorage.setItem(LS.SCHEMA, String(envSchema));
      }
    }
  } catch {
    // ignore
  }
}

export async function postJSON<T>(url: string, body: unknown, extra: HeadersMap = {}): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'x-api-key': getStoredKey(),
    'x-schema-version': getStoredSchema(),
    ...extra,
  };
  const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
  const respSchema = r.headers.get('x-schema-version');
  if (respSchema) setStoredSchema(respSchema);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const data = (await r.json()) as T & { schema?: string };
  if (data?.schema) setStoredSchema(data.schema);
  return data;
}

export async function getHealth(base: string) {
  const r = await fetch(`${base}/health`, { method: 'GET' });
  const j = await r.json().catch(() => ({}));
  if (j?.schema) setStoredSchema(j.schema);
  return j;
}
