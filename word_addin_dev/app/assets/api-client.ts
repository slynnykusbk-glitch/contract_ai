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
import { registerFetch, deregisterFetch, registerTimer, deregisterTimer, withBusy } from './pending.ts';
import { checkHealth } from './health.ts';
import { notifyWarn } from './notifier.ts';

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

export async function logApiClientChecksum() {
  const url = new URL(import.meta.url).toString();
  try {
    const res = await fetch(url);
    const text = await res.text();
    const buf = new TextEncoder().encode(text);
    const hashBuf = await crypto.subtle.digest('SHA-256', buf);
    const hash = Array.from(new Uint8Array(hashBuf))
      .slice(0, 4)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    console.log(`[selftest] api-client.js ${hash} ${url}`);
  } catch {
    console.log(`[selftest] api-client.js fail ${url}`);
  }
}

const DEFAULT_BASE = 'https://localhost:9443';
function base(): string {
  try { return (localStorage.getItem('backendUrl') || DEFAULT_BASE).replace(/\/+$/, ''); }
  catch { return DEFAULT_BASE; }
}

const ANALYZE_BASE_MS = 9000;
const ANALYZE_PER_KB_MS = 60;
const ANALYZE_MAX_MS = 90000;
const ANALYZE_RETRY_COUNT = 1;
const ANALYZE_RETRY_BACKOFF_MS = 3000;

export async function postJSON(path: string, body: any, timeoutOverride?: number) {
  return withBusy(async () => {
    const url = base() + path;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const schema = getSchemaFromStore() || '1.4';
    headers['x-schema-version'] = schema;
    const key = getApiKeyFromStore();
    if (key) headers['x-api-key'] = key;

    const bodyStr = JSON.stringify(body || {});
    const sizeBytes = new TextEncoder().encode(bodyStr).length;

    let timeoutMs = timeoutOverride;
    let retryCount = ANALYZE_RETRY_COUNT;
    let backoffMs = ANALYZE_RETRY_BACKOFF_MS;

    if (path === '/api/analyze') {
      if (timeoutMs == null) {
        const dyn = ANALYZE_BASE_MS + ANALYZE_PER_KB_MS * (sizeBytes / 1024);
        timeoutMs = Math.max(ANALYZE_BASE_MS, Math.min(ANALYZE_MAX_MS, Math.floor(dyn)));
      }
      try {
        for (const k of [
          'cai.timeout.analyze.ms',
          'cai_timeout_ms:/api/analyze',
          'cai_timeout_ms:analyze',
        ]) {
          const v = localStorage.getItem(k);
          if (v) {
            const parsed = parseInt(v, 10);
            if (Number.isFinite(parsed)) {
              timeoutMs = parsed;
              break;
            }
          }
        }
      } catch {}
      try {
        const v = localStorage.getItem('cai.retry.analyze.count');
        if (v) retryCount = parseInt(v, 10);
      } catch {}
      try {
        const v = localStorage.getItem('cai.retry.analyze.backoff.ms');
        if (v) backoffMs = parseInt(v, 10);
      } catch {}
      try {
        const params = new URLSearchParams(location.search);
        const ta = params.get('ta');
        if (ta) timeoutMs = parseInt(ta, 10);
        const rac = params.get('rac');
        if (rac) retryCount = parseInt(rac, 10);
        const rb = params.get('rb');
        if (rb) backoffMs = parseInt(rb, 10);
      } catch {}
    }
    timeoutMs = timeoutMs ?? ANALYZE_BASE_MS;

    async function attempt(n: number): Promise<any> {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(`timeout ${timeoutMs}ms`), timeoutMs!);
      registerFetch(ctrl);
      registerTimer(t);
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers,
          body: bodyStr,
          credentials: 'include',
          signal: ctrl.signal,
        });
        const json = await resp.json().catch(() => ({}));
        if (resp.status === 422) {
          console.warn('[analyze] 422', json.detail);
          const msg = Array.isArray(json?.detail) ? json.detail.map((d: any) => d.msg).join('; ') : json?.detail;
          try { notifyWarn(`Validation error: ${msg}`); } catch {}
        }
        if (path === '/api/analyze' && (resp.status === 504 || resp.status >= 500) && n < retryCount) {
          await new Promise(res => setTimeout(res, backoffMs));
          return attempt(n + 1);
        }
        return { resp, json };
      } catch (e: any) {
        if (path === '/api/analyze' && e?.name === 'AbortError') {
          const reason = ctrl.signal.reason || 'aborted';
          console.log(`[NET] analyze aborted: ${reason}`);
          if (n < retryCount && String(reason).startsWith('timeout')) {
            await new Promise(res => setTimeout(res, backoffMs));
            return attempt(n + 1);
          }
          throw new DOMException(reason, 'AbortError');
        }
        throw e;
      } finally {
        clearTimeout(t);
        deregisterTimer(t);
        deregisterFetch(ctrl);
      }
    }

    return attempt(0);
  });
}
export { postJSON as postJson };
;(window as any).postJson = postJSON;

async function req(path: string, { method='GET', body=null, key=path, timeoutMs=9000 }: { method?: string; body?: any; key?: string; timeoutMs?: number } = {}) {
  return withBusy(async () => {
    const headers: Record<string, string> = { 'Content-Type':'application/json' };
    const apiKey = getApiKeyFromStore();
    if (apiKey) headers['x-api-key'] = apiKey;
    headers['x-schema-version'] = getSchemaFromStore() || '1.4';

    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort('timeout'), timeoutMs);
    registerFetch(ctrl);
    registerTimer(t);
    let r: Response;
    try {
      r = await fetch(base()+path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        credentials: 'include',
        signal: ctrl.signal,
      });
    } finally {
      clearTimeout(t);
      deregisterTimer(t);
      deregisterFetch(ctrl);
    }
    const json = await r.json().catch(() => ({}));
    const meta = metaFromResponse({ headers: r.headers, json, status: r.status });
    try { applyMetaToBadges(meta); } catch {}
    try {
      const w = window as any;
      if (!w.__last) w.__last = {};
      w.__last[key] = { status: r.status, req: { path, method, body }, json };
    } catch {}
    return { ok: r.ok, json, resp: r, meta };
  });
}

export async function apiHealth(backend?: string) {
  return withBusy(() => checkHealth({ backend }));
}

export async function analyze(payload: any = {}) {
  const body = {
    text:  payload?.text ?? payload?.content,
    mode:  payload?.mode ?? 'live',
    schema: payload?.schema ?? '1.4',
  };
  const { resp, json } = await postJSON('/api/analyze', body);
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try { applyMetaToBadges(meta); } catch {}
  try {
    const w = window as any; if (!w.__last) w.__last = {};
    w.__last.analyze = { status: resp.status, req: { path: '/api/analyze', method: 'POST', body }, json };
  } catch {}
  return { ok: resp.ok, json, resp, meta };
}

export async function apiAnalyze(text: string) {
  return analyze({ text });
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
