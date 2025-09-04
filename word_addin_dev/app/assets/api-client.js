// === meta helpers for panel (ESM) ===
export function metaFromResponse(resp) {
  const h = resp.headers;
  const get = (n) => h.get(n) || null;
  return {
    cid: get('x-cid'),
    xcache: get('x-cache'),
    latencyMs: Number(get('x-latency-ms')) || null,
    schema: get('x-schema-version'),
    provider: get('x-provider'),
    model: get('x-model'),
    llm_mode: get('x-llm-mode'),
    usage: get('x-usage-total'),
  };
}

export function applyMetaToBadges(m) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (v ?? '—');
  };
  set('cid', m.cid);
  set('xcache', m.xcache);
  set('latency', m.latencyMs == null ? '—' : String(m.latencyMs));
  set('schema', m.schema);
  set('provider', m.provider);
  set('model', m.model);
  set('mode', m.llm_mode);
  set('usage', m.usage);
}

// минимальный API-клиент под панель (ESM)
const DEFAULT_BASE = 'https://localhost:9443';
function base() {
  try { return (localStorage.getItem('backendUrl') || DEFAULT_BASE).replace(/\/+$/,''); }
  catch { return DEFAULT_BASE; }
}
async function req(path, { method='GET', body=null } = {}) {
  const r = await fetch(base()+path, {
    method,
    headers: { 'content-type':'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include'
  });
  const json = await r.json().catch(() => ({}));
  return { ok: r.ok, json, resp: r };
}

export async function apiHealth()      { const {ok,json,resp} = await req('/health');      return {ok,json,meta: metaFromResponse(resp)}; }
export async function apiAnalyze(text) { const {ok,json,resp} = await req('/api/analyze',   {method:'POST', body:{text, mode:'live'}}); return {ok,json,meta: metaFromResponse(resp)}; }
export async function apiGptDraft(text){ const {ok,json,resp} = await req('/api/gpt-draft', {method:'POST', body:{text, mode:'friendly'}}); return {ok,json,meta: metaFromResponse(resp)}; }
export async function apiQaRecheck(text,rules=[]){ const {ok,json,resp}=await req('/api/qa-recheck',{method:'POST', body:{text, rules}}); return {ok,json,meta: metaFromResponse(resp)}; }

//////////////////////////////////////////////////////////////////////////
// Конец файла
//////////////////////////////////////////////////////////////////////////
