// app/assets/api-client.ts
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
var DEFAULT_BASE = "https://localhost:9443";
function base() {
  try {
    return (localStorage.getItem("backendUrl") || DEFAULT_BASE).replace(/\/+$/, "");
  } catch {
    return DEFAULT_BASE;
  }
}
async function req(path, { method = "GET", body = null, key = path } = {}) {
  const headers = { "content-type": "application/json" };
  try {
    const apiKey = localStorage.getItem("api_key");
    if (apiKey) headers["x-api-key"] = apiKey;
  } catch {}
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
async function apiAnalyze(text) {
  return req("/api/analyze", { method: "POST", body: { text, mode: "live" }, key: "analyze" });
}
async function apiGptDraft(text, mode = "friendly", extra = {}) {
  return req("/api/gpt-draft", { method: "POST", body: { text, mode, ...extra }, key: "gpt-draft" });
}
async function apiQaRecheck(text, rules = []) {
  return req("/api/qa-recheck", { method: "POST", body: { text, rules }, key: "qa-recheck" });
}
export {
  apiAnalyze,
  apiGptDraft,
  apiHealth,
  apiQaRecheck,
  applyMetaToBadges,
  metaFromResponse,
  parseFindings
};
