// word_addin_dev/app/assets/api-client.ts
function parseFindings(resp) {
  const arr = resp?.analysis?.findings ?? resp?.findings ?? resp?.issues ?? [];
  return Array.isArray(arr) ? arr.filter(Boolean) : [];
}
window.parseFindings = parseFindings;
function metaFromResponse(r) {
  const h = r.headers;
  const js = r.json || {};
  const llm = js.llm || js;
  return {
    cid: h.get("x-cid"),
    xcache: h.get("x-cache"),
    latencyMs: h.get("x-latency-ms"),
    schema: h.get("x-schema-version"),
    provider: h.get("x-provider") || llm.provider || js.provider || null,
    model: h.get("x-model") || llm.model || js.model || null,
    llm_mode: h.get("x-llm-mode") || llm.mode || js.mode || null,
    usage: h.get("x-usage-total"),
    status: r.status != null ? String(r.status) : null
  };
}
function applyMetaToBadges(m) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v && v.length ? v : "\u2014";
  };
  set("status", m.status);
  set("cid", m.cid);
  set("xcache", m.xcache);
  set("latency", m.latencyMs);
  set("schema", m.schema);
  set("provider", m.provider);
  set("model", m.model);
  set("mode", m.llm_mode);
  set("usage", m.usage);
}
async function logApiClientChecksum() {
  const url = new URL(import.meta.url).toString();
  try {
    const res = await fetch(url);
    const text = await res.text();
    const buf = new TextEncoder().encode(text);
    const hashBuf = await crypto.subtle.digest("SHA-256", buf);
    const hash = Array.from(new Uint8Array(hashBuf)).slice(0, 4).map(b => b.toString(16).padStart(2, "0")).join("");
    console.log(`[selftest] api-client.js ${hash} ${url}`);
  } catch {
    console.log(`[selftest] api-client.js fail ${url}`);
  }
}
var DEFAULT_BASE = "https://localhost:9443";
function base() {
  try {
    return (localStorage.getItem("backendUrl") || DEFAULT_BASE).replace(/\/+$/, "");
  } catch {
    return DEFAULT_BASE;
  }
}
async function postJson(path, body, opts = {}) {
  const url = base() + path;
  const headers = { "content-type": "application/json" };
  const apiKey = opts.apiKey ?? (() => {
    try {
      const storeKey = window.CAI?.Store?.get?.()?.apiKey;
      if (storeKey) return storeKey;
    } catch {
    }
    try {
      return localStorage.getItem("api_key") || "";
    } catch {
      return "";
    }
  })();
  if (apiKey) {
    headers["x-api-key"] = apiKey;
    try {
      localStorage.setItem("api_key", apiKey);
    } catch {
    }
    try {
      window.CAI?.Store?.setApiKey?.(apiKey);
    } catch {
    }
  }
  const schemaVersion = opts.schemaVersion ?? (() => {
    try {
      const storeSchema = window.CAI?.Store?.get?.()?.schemaVersion;
      if (storeSchema) return storeSchema;
    } catch {
    }
    try {
      return localStorage.getItem("schema_version") || "";
    } catch {
      return "";
    }
  })();
  if (schemaVersion) headers["x-schema-version"] = schemaVersion;
  const http = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body || {}),
    credentials: "include"
  });
  const json = await http.json().catch(() => ({}));
  const hdr = http.headers;
  try {
    window.CAI?.Store?.setMeta?.({ cid: hdr.get("x-cid") || void 0, schema: hdr.get("x-schema-version") || void 0 });
  } catch {
  }
  return { http, json, headers: hdr };
}
window.postJson = postJson;
async function req(path, { method = "GET", body = null, key = path } = {}) {
  const headers = { "content-type": "application/json" };
  try {
    const store = window.CAI?.Store?.get?.() || {};
    const apiKey = store.apiKey || localStorage.getItem("api_key");
    if (apiKey) headers["x-api-key"] = apiKey;
    const schema = store.schemaVersion || localStorage.getItem("schema_version");
    if (schema) headers["x-schema-version"] = schema;
  } catch {
  }
  const r = await fetch(base() + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : void 0,
    credentials: "include"
  });
  const json = await r.json().catch(() => ({}));
  const meta = metaFromResponse({ headers: r.headers, json, status: r.status });
  try {
    applyMetaToBadges(meta);
  } catch {
  }
  try {
    const w = window;
    if (!w.__last) w.__last = {};
    w.__last[key] = { status: r.status, req: { path, method, body }, json };
  } catch {
  }
  return { ok: r.ok, json, resp: r, meta };
}
async function apiHealth() {
  return req("/health", { key: "health" });
}
async function analyze(payload = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Schema-Version": "1.4"
  };
  const key = getApiKeyFromStore();
  if (key) headers["X-Api-Key"] = key;
  const body = { payload: { schema: "1.4", mode: (payload == null ? void 0 : payload.mode) ?? "live" } };
  const text = (payload == null ? void 0 : payload.text) ?? (payload == null ? void 0 : payload.content);
  if (text) body.payload.text = text;
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers,
    body: JSON.stringify(body)
  });
  const json = await resp.json().catch(() => ({}));
  const meta = metaFromResponse({ headers: resp.headers, json, status: resp.status });
  try {
    applyMetaToBadges(meta);
  } catch {
  }
  try {
    const w = window;
    if (!w.__last) w.__last = {};
    w.__last.analyze = { status: resp.status, req: { path: "/api/analyze", method: "POST", body }, json };
  } catch {
  }
  return { ok: resp.ok, json, resp, meta };
}
async function apiAnalyze(text) {
  return analyze({ text });
}
async function apiGptDraft(cid, clause, mode = "friendly") {
  return req("/api/gpt-draft", { method: "POST", body: { cid, clause, mode }, key: "gpt-draft" });
}
async function apiSummary(cid) {
  return req("/api/summary", { method: "POST", body: { cid }, key: "summary" });
}
async function apiSummaryGet() {
  return req("/api/summary", { method: "GET", key: "summary" });
}
async function apiQaRecheck(text, rules = {}) {
  const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : rules || {};
  return req("/api/qa-recheck", { method: "POST", body: { text, rules: dict }, key: "qa-recheck" });
}
async function postRedlines(before_text, after_text) {
  const fn = window.postJson || postJson;
  return fn("/api/panel/redlines", { before_text, after_text });
}
export {
  analyze,
  apiAnalyze,
  apiGptDraft,
  apiHealth,
  apiQaRecheck,
  apiSummary,
  apiSummaryGet,
  applyMetaToBadges,
  logApiClientChecksum,
  metaFromResponse,
  parseFindings,
  postJson,
  postRedlines
};
