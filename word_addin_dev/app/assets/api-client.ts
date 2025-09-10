export type Meta = {
  cid?: string | null;
  xcache?: string | null;
  latencyMs?: string | null;
  schema?: string | null;
  provider?: string | null;
  model?: string | null;
  llm_mode?: string | null;
  usage?: string | null;
  status?: string | null;
};

export type AnalyzeFinding = {
  rule_id: string;
  clause_type?: string;
  severity?: "low" | "medium" | "high" | "critical" | string;
  start?: number;
  end?: number;
  snippet?: string;
  advice?: string;
  law_refs?: string[];
  law_reference?: string; // legacy
  citations?: string[];
  conflict_with?: string[];
  category?: string;
  score?: number;
  suggestion?: { text?: string };
  ops?: { start?: number; end?: number; replacement?: string }[];
  scope?: { unit?: string; nth?: number };
  occurrences?: number;
};

export type AnalyzeResponse = {
  status: "ok" | "OK";
  analysis?: { findings?: AnalyzeFinding[] };
  findings?: AnalyzeFinding[];
  issues?: AnalyzeFinding[];
  meta?: any;
};

export function parseFindings(resp: AnalyzeResponse): AnalyzeFinding[] {
  const arr = resp?.analysis?.findings ?? resp?.findings ?? resp?.issues ?? [];
  return Array.isArray(arr) ? arr.filter(Boolean) : [];
}

// (dev aid; harmless in prod)
;(window as any).parseFindings = parseFindings;

export function metaFromResponse(r: { headers: Headers; json?: any; status?: number }): Meta {
  const h = r.headers;
  const js = r.json || {};
  const llm = js.llm || js;
  return {
    cid:       h.get('x-cid'),
    xcache:    h.get('x-cache'),
    latencyMs: h.get('x-latency-ms'),
    schema:    h.get('x-schema-version'),
    provider:  h.get('x-provider') || llm.provider || js.provider || null,
    model:     h.get('x-model') || llm.model || js.model || null,
    llm_mode:  h.get('x-llm-mode') || llm.mode || js.mode || null,
    usage:     h.get('x-usage-total'),
    status:    r.status != null ? String(r.status) : null,
  };
}

export function applyMetaToBadges(m: Meta) {
  const set = (id: string, v?: string | null) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v && v.length ? v : '—';
  };
  set('status',    m.status);
  set('cid',       m.cid);
  set('xcache',    m.xcache);
  set('latency',   m.latencyMs);
  set('schema',    m.schema);
  set('provider',  m.provider);
  set('model',     m.model);
  set('mode',      m.llm_mode);
  set('usage',     m.usage);
}

const DEFAULT_BASE = 'https://localhost:9443';
function base(): string {
  try { return (localStorage.getItem('backendUrl') || DEFAULT_BASE).replace(/\/+$/, ''); }
  catch { return DEFAULT_BASE; }
}

export async function postJson(path: string, body: any, opts: { apiKey?: string; schemaVersion?: string } = {}) {
  const url = base() + path;
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  const apiKey = opts.apiKey ?? (() => {
    try {
      const storeKey = (window as any).CAI?.Store?.get?.()?.apiKey;
      if (storeKey) return storeKey;
    } catch {}
    try { return localStorage.getItem('api_key') || ''; } catch { return ''; }
  })();
  if (apiKey) {
    headers['x-api-key'] = apiKey;
    try { localStorage.setItem('api_key', apiKey); } catch {}
    try { (window as any).CAI?.Store?.setApiKey?.(apiKey); } catch {}
  }
  const schemaVersion = opts.schemaVersion ?? (() => {
    try {
      const storeSchema = (window as any).CAI?.Store?.get?.()?.schemaVersion;
      if (storeSchema) return storeSchema;
    } catch {}
    try { return localStorage.getItem('schema_version') || ''; } catch { return ''; }
  })();
  if (schemaVersion) headers['x-schema-version'] = schemaVersion;
  const http = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body || {}),
    credentials: 'include',
  });
  const json = await http.json().catch(() => ({}));
  const hdr = http.headers;
  try {
    (window as any).CAI?.Store?.setMeta?.({ cid: hdr.get('x-cid') || undefined, schema: hdr.get('x-schema-version') || undefined });
  } catch {}
  return { http, json, headers: hdr };
}
;(window as any).postJson = postJson;

async function req(path: string, { method='GET', body=null, key=path }: { method?: string; body?: any; key?: string } = {}) {
  const headers: Record<string, string> = { 'content-type':'application/json' };
  try {
    const store = (window as any).CAI?.Store?.get?.() || {};
    const apiKey = store.apiKey || localStorage.getItem('api_key');
    if (apiKey) headers['x-api-key'] = apiKey;
    const schema = store.schemaVersion || localStorage.getItem('schema_version');
    if (schema) headers['x-schema-version'] = schema;
  } catch {}

  const r = await fetch(base()+path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include'
  });
  const json = await r.json().catch(() => ({}));
  const meta = metaFromResponse({ headers: r.headers, json, status: r.status });
  try { applyMetaToBadges(meta); } catch {}
  try {
    const w = window as any;
    if (!w.__last) w.__last = {};
    w.__last[key] = { status: r.status, req: { path, method, body }, json };
  } catch {}
  return { ok: r.ok, json, resp: r, meta };
}

export async function apiHealth() {
  return req('/health', { key: 'health' });
}

export async function apiAnalyze(text: string) {
  return req('/api/analyze', { method: 'POST', body: { text }, key: 'analyze' });
}

export async function apiGptDraft(cid: string, clause: string, mode = 'friendly') {
  return req('/api/gpt-draft', { method: 'POST', body: { cid, clause, mode }, key: 'gpt-draft' });
}

export async function apiSummary(cid: string) {
  return req('/api/summary', { method: 'POST', body: { cid }, key: 'summary' });
}

export async function apiSummaryGet() {
  return req('/api/summary', { method: 'GET', key: 'summary' });
}

export async function apiQaRecheck(text: string, rules: any = {}) {
  const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : (rules || {});
  return req('/api/qa-recheck', { method: 'POST', body: { text, rules: dict }, key: 'qa-recheck' });
}

export async function postRedlines(before_text: string, after_text: string) {
  const fn: any = (window as any).postJson || postJson;
  return fn('/api/panel/redlines', { before_text, after_text });
}
