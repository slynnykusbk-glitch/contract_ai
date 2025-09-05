// === meta helpers and API client for panel (ESM) ===
export function metaFromResponse(r) {
  const h = r.headers;
  const js = r.json || {};
  const llm = js.llm || js;
  return {
    cid: h.get('x-cid'),
    xcache: h.get('x-cache'),
    latencyMs: h.get('x-latency-ms'),
    schema: h.get('x-schema-version'),
    provider: h.get('x-provider') || llm.provider || js.provider || null,
    model: h.get('x-model') || llm.model || js.model || null,
    llm_mode: h.get('x-llm-mode') || llm.mode || js.mode || null,
    usage: h.get('x-usage-total'),
    status: r.status != null ? String(r.status) : null,
  };
}

export function applyMetaToBadges(m) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v && v.length ? v : '—';
  };
  set('status', m.status);
  set('cid', m.cid);
  set('xcache', m.xcache);
  set('latency', m.latencyMs);
  set('schema', m.schema);
  set('provider', m.provider);
  set('model', m.model);
  set('mode', m.llm_mode);
  set('usage', m.usage);
}

// минимальный API-клиент под панель (ESM)
const DEFAULT_BASE = 'https://localhost:9443';
function base() {
  try { return (localStorage.getItem('backendUrl') || DEFAULT_BASE).replace(/\/+$/, ''); }
  catch { return DEFAULT_BASE; }
}

async function req(path, { method='GET', body=null, key=path } = {}) {
  const r = await fetch(base()+path, {
    method,
    headers: { 'content-type':'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include'
  });
  const json = await r.json().catch(() => ({}));
  const meta = metaFromResponse({ headers: r.headers, json, status: r.status });
  try { applyMetaToBadges(meta); } catch {}
  try {
    const w = window;
    w.__last = w.__last || {};
    w.__last[key] = { status: r.status, req: { path, method, body }, json };
  } catch {}
  return { ok: r.ok, json, resp: r, meta };
}

export async function apiHealth() {
  const { ok, json, resp, meta } = await req('/health', { key: 'health' });
  return { ok, json, resp, meta };
}
export async function apiAnalyze(text) {
  const { ok, json, resp, meta } = await req('/api/analyze', { method: 'POST', body: { text, mode: 'live' }, key: 'analyze' });
  return { ok, json, resp, meta };
}
export async function apiGptDraft(text, mode='friendly', extra={}) {
  const { ok, json, resp, meta } = await req('/api/gpt-draft', { method: 'POST', body: { text, mode, ...extra }, key: 'gpt-draft' });
  return { ok, json, resp, meta };
}
export async function apiQaRecheck(text, rules=[]) {
  const { ok, json, resp, meta } = await req('/api/qa-recheck', { method: 'POST', body: { text, rules }, key: 'qa-recheck' });
  return { ok, json, resp, meta };
}
