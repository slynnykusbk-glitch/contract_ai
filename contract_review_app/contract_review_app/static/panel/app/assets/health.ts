let cached: Promise<any> | null = null;

export async function checkHealth(opts: { backend?: string; timeoutMs?: number } = {}) {
  if (!cached) {
    const backend = (opts.backend || '').replace(/\/+$/, '');
    const url = backend ? `${backend}/health` : '/health';
    const ctrl = new AbortController();
    const timeout = opts.timeoutMs ?? 9000;
    const t = setTimeout(() => ctrl.abort(), timeout);
    cached = fetch(url, { signal: ctrl.signal }).then(async resp => {
      clearTimeout(t);
      const json = await resp.json().catch(() => ({}));
      return { ok: resp.ok, json, resp };
    });
  }
  return cached;
}
