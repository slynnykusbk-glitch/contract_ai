// === meta helpers and API client for panel (ESM) ===

export function metaFromResponse(res) {
  const h = res?.headers || new Headers();
  const pick = (name) => {
    const v = h.get(name);
    return v == null ? '' : v;
  };
  return {
    provider: pick('x-provider'),
    model: pick('x-model'),
    mode: pick('x-llm-mode'),
    usage: pick('x-usage-total'),
    schema: pick('x-schema-version'),
    latency: pick('x-latency-ms'),
    cid: pick('x-cid'),
    xcache: pick('x-cache')
  };
}

export function applyMetaToBadges(meta) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v && v.length ? v : '—';
  };
  set('cidBadge', meta.cid); set('cid', meta.cid);
  set('xcacheBadge', meta.xcache); set('xcache', meta.xcache);
  set('latencyBadge', meta.latency); set('latency', meta.latency);
  set('schemaBadge', meta.schema); set('schema', meta.schema);
  set('providerBadge', meta.provider); set('provider', meta.provider);
  set('modelBadge', meta.model); set('model', meta.model);
  set('modeBadge', meta.mode); set('mode', meta.mode);
  set('usageBadge', meta.usage); set('usage', meta.usage);
}

export function parseFindings(resp) {
  const arr = resp?.analysis?.findings ?? resp?.findings ?? resp?.issues ?? [];
  return Array.isArray(arr) ? arr.filter(Boolean) : [];
}

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
  try {
    const w = window;
    w.__last = w.__last || {};
    w.__last[key] = { status: r.status, req: { path, method, body }, json };
  } catch {}
  return { ok: r.ok, json, resp: r };
}

export async function apiHealth() {
  return await req('/health', { key: 'health' });
}

export async function apiAnalyze(text) {
  return await req('/api/analyze', { method: 'POST', body: { text, mode: 'live' }, key: 'analyze' });
}

export async function apiGptDraft(text, mode='friendly', extra={}) {
  return await req('/api/gpt-draft', { method: 'POST', body: { text, mode, ...extra }, key: 'gpt-draft' });
}

export async function apiQaRecheck(text, rules=[]) {
  return await req('/api/qa-recheck', { method: 'POST', body: { text, rules }, key: 'qa-recheck' });
}

