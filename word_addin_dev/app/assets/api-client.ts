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

import { getApiKeyFromStore, getSchemaFromStore } from "./store.ts";

export type AnalyzeFinding = {
  rule_id: string;
  clause_type?: string;
  severity?: "low" | "medium" | "high" | "critical" | string;
  start?: number;
  end?: number;
  snippet?: string;
  normalized_snippet?: string;
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

export async function postJSON(path: string, body: any) {
  const url = base() + path;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const schema = getSchemaFromStore() || '1.4';
  headers['x-schema-version'] = schema;
  const key = getApiKeyFromStore();
  if (key) headers['x-api-key'] = key;
  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body || {}),
    credentials: 'include',
  });
  const json = await resp.json().catch(() => ({}));
  return { resp, json };
}
export { postJSON as postJson };
;(window as any).postJson = postJSON;

async function req(path: string, { method='GET', body=null, key=path }: { method?: string; body?: any; key?: string } = {}) {
  const headers: Record<string, string> = { 'Content-Type':'application/json' };
  const apiKey = getApiKeyFromStore();
  if (apiKey) headers['x-api-key'] = apiKey;
  headers['x-schema-version'] = getSchemaFromStore() || '1.4';

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
  const { resp, json } = await postJSON('/api/analyze', { text });
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try { applyMetaToBadges(meta); } catch {}
  return { ok: resp.ok, json, resp, meta };
}

export async function apiGptDraft(cid: string, clause: string, mode = 'friendly') {
  const { resp, json } = await postJSON('/api/gpt-draft', { cid, clause, mode });
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try { applyMetaToBadges(meta); } catch {}
  return { ok: resp.ok, json, resp, meta };
}

export async function apiSummary(cid: string) {
  return req('/api/summary', { method: 'POST', body: { cid }, key: 'summary' });
}

export async function apiSummaryGet() {
  return req('/api/summary', { method: 'GET', key: 'summary' });
}

export async function apiQaRecheck(text: string, rules: any = {}) {
  const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : (rules || {});
  const { resp, json } = await postJSON('/api/qa-recheck', { text, rules: dict });
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try { applyMetaToBadges(meta); } catch {}
  return { ok: resp.ok, json, resp, meta };
}

export async function postRedlines(before_text: string, after_text: string) {
  return postJSON('/api/panel/redlines', { before_text, after_text });
}
