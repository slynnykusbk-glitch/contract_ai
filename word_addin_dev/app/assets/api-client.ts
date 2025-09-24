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

import type { components } from "../types/api";
import { getApiKeyFromStore, getSchemaFromStore } from "./store.ts";
import { registerFetch, deregisterFetch, registerTimer, deregisterTimer, withBusy } from './pending.ts';
import { checkHealth } from './health.ts';
import { notifyWarn } from './notifier';

const DEV_MODE = (() => {
  try {
    const ls = localStorage.getItem('cai_dev');
    if (ls === '1') return true;
    const params = new URLSearchParams(globalThis.location?.search || '');
    return params.get('debug') === '1';
  } catch { return false; }
})();

function logError(msg: string, err: any, extra?: any) {
  if (DEV_MODE) {
    console.error(msg, err, extra);
  } else {
    console.error(msg, err);
  }
}

export type AnalyzeFinding = components["schemas"]["Finding"] & Record<string, any>;


export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"] & Record<string, any>;

export function parseFindings(resp: AnalyzeResponse | Findings): Findings {
  if (Array.isArray(resp)) return resp.filter(Boolean);
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

const DEFAULT_BASE = 'https://127.0.0.1:9443';
function base(): string {
  try { return (localStorage.getItem('backendUrl') || DEFAULT_BASE).replace(/\/+$/, ''); }
  catch { return DEFAULT_BASE; }
}

export async function getTrace(cid: string): Promise<any | undefined> {
  if (!cid) return undefined;
  const url = `${base()}/api/trace/${cid}`;
  try {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) return undefined;
    return await res.json();
  } catch (err) {
    logError('[trace] fetch failed', err);
    return undefined;
  }
}

export function computeAnalyzeTimeout(textBytes: number): number {
  const BASE = 28_000;   // 28с базово
  const PER_KB = 50;     // +50мс за каждый КБ текста
  const CEIL = 120_000;  // потолок 120с
  const kb = Math.ceil((textBytes || 0) / 1024);
  return Math.min(CEIL, BASE + PER_KB * kb);
}

const DEFAULT_TIMEOUT_MS = 9000;
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

    const bodyWithSchema = { ...(body || {}), schema };
    const bodyStr = JSON.stringify(bodyWithSchema);
    const sizeBytes = new TextEncoder().encode(bodyStr).length;

    let timeoutMs = timeoutOverride;
    let retryCount = ANALYZE_RETRY_COUNT;
    let backoffMs = ANALYZE_RETRY_BACKOFF_MS;

    if (path === '/api/analyze') {
      if (timeoutMs == null) {
        timeoutMs = computeAnalyzeTimeout(sizeBytes);
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
    timeoutMs = timeoutMs ?? DEFAULT_TIMEOUT_MS;

    async function attempt(n: number): Promise<any> {
      const ctrl = new AbortController();
      (ctrl as any).__key = path;
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
        logError(`[NET] ${path} failed`, e, { body: bodyWithSchema });
        try {
          const msg = DEV_MODE ? String(e) : 'Analysis failed, please try again';
          notifyWarn(msg);
        } catch {}
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
    const schema = getSchemaFromStore() || '1.4';
    headers['x-schema-version'] = schema;

    const payload = body && method !== 'GET' ? { ...body, schema } : method !== 'GET' ? { schema } : undefined;

    const ctrl = new AbortController();
    (ctrl as any).__key = path;
    const t = setTimeout(() => ctrl.abort('timeout'), timeoutMs);
    registerFetch(ctrl);
    registerTimer(t);
    let r: Response;
    try {
      r = await fetch(base()+path, {
        method,
        headers,
        body: payload ? JSON.stringify(payload) : undefined,
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
      w.__last[key] = { status: r.status, req: { path, method, body: payload }, json };
    } catch {}
    return { ok: r.ok, json, resp: r, meta };
  });
}

export async function apiHealth(backend?: string) {
  return withBusy(() => checkHealth({ backend }));
}

export async function analyze(opts: any = {}) {
  const body = {
    text:  opts?.text ?? opts?.content,
    mode:  opts?.mode ?? 'live',
    risk:  opts?.risk ?? 'medium',
  };
  let textBytes = 0;
  const guessBytes = (input: unknown): number => {
    if (!input) return 0;
    if (typeof input === 'string') return new TextEncoder().encode(input).length;
    if (typeof input === 'number' && Number.isFinite(input)) return input;
    if (typeof input === 'object') {
      const anyObj = input as Record<string, unknown>;
      if (typeof anyObj.text === 'string') return new TextEncoder().encode(anyObj.text).length;
      if (anyObj.text && typeof (anyObj.text as any).length === 'number') return Number((anyObj.text as any).length) || 0;
    }
    return 0;
  };
  try {
    const w = window as any;
    textBytes = guessBytes(w?.__lastAnalyzed);
    if (!textBytes) {
      const metaBytes = w?.__last?.analyze?.json?.meta?.text_bytes ?? w?.__last?.analyze?.json?.meta?.textBytes;
      textBytes = guessBytes(metaBytes);
    }
  } catch {}
  if (!textBytes) {
    textBytes = guessBytes(body.text);
  }
  const timeoutMs = computeAnalyzeTimeout(textBytes);
  const { resp, json } = await postJSON('/api/analyze', body, timeoutMs);
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

export async function apiGptDraft(clause_id: string, text: string, mode = 'friendly') {
  const { resp, json } = await postJSON('/api/gpt-draft', { clause_id, text, mode });
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


export async function apiQaRecheck(
  input: { document_id?: string; text?: string; rules?: any; risk?: string } | string,
  rules: any = {},
) {
  let payload: any;
  let risk: string | undefined;
  if (typeof input === 'string') {
    payload = { text: input };
  } else {
    payload = input.document_id ? { document_id: input.document_id } : { text: input.text };
    rules = input.rules ?? {};
    risk = input.risk ?? risk;
  }
  const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : (rules || {});
  const body = { ...payload, rules: dict };
  if (risk) body.risk = risk;
  const { resp, json } = await postJSON('/api/qa-recheck', body);
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try { applyMetaToBadges(meta); } catch {}
  return { ok: resp.ok, json, resp, meta };
}

export async function postRedlines(before_text: string, after_text: string) {
  return postJSON('/api/panel/redlines', { before_text, after_text });
}
