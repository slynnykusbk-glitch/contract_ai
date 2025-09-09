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
async function postJson(path, body, opts = {}) {
  const url = base() + path;
  const headers = { "content-type": "application/json" };
  const apiKey = opts.apiKey ?? (() => { try { return localStorage.getItem("api_key") || ""; } catch { return ""; } })();
  if (apiKey) {
    headers["x-api-key"] = apiKey;
    try { localStorage.setItem("api_key", apiKey); } catch {}
    try { window.CAI?.Store?.setApiKey?.(apiKey); } catch {}
  }
  const schemaVersion = opts.schemaVersion ?? (() => { try { return localStorage.getItem("schemaVersion") || ""; } catch { return ""; } })();
  if (schemaVersion) headers["x-schema-version"] = schemaVersion;
  const http = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body || {}),
    credentials: "include"
  });
  const json = await http.json().catch(() => ({}));
  try {
    const h = http.headers;
    window.CAI?.Store?.setMeta?.({ cid: h.get("x-cid") || void 0, schema: h.get("x-schema-version") || void 0 });
  } catch {}
  return { http, json, headers: http.headers };
}
window.postJson = postJson;
async function req(path, { method = "GET", body = null, key = path } = {}) {
  const headers = { "content-type": "application/json" };
  try {
    const apiKey = localStorage.getItem("api_key");
    if (apiKey) headers["x-api-key"] = apiKey;
  } catch {}
  try {
    const schema = localStorage.getItem("schemaVersion");
    if (schema) headers["x-schema-version"] = schema;
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
  return req("/api/analyze", { method: "POST", body: { text }, key: "analyze" });
}
async function apiGptDraft(cid, clause, mode = "friendly") {
  return req("/api/gpt-draft", { method: "POST", body: { cid, clause, mode }, key: "gpt-draft" });
}
async function apiQaRecheck(text, rules = {}) {
  const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : (rules || {});
  return req("/api/qa-recheck", { method: "POST", body: { text, rules: dict }, key: "qa-recheck" });
}
async function apiSummary(cid) {
  return req("/api/summary", { method: "POST", body: { cid }, key: "summary" });
}
async function apiSummaryGet() {
  return req("/api/summary", { method: "GET", key: "summary" });
}
async function apiSuggestEdits(text, findings = []) {
  const body = { text };
  if (Array.isArray(findings) && findings.length) body.findings = findings;
  return req("/api/suggest_edits", { method: "POST", body, key: "suggest_edits" });
}
async function postRedlines(before_text, after_text) {
  const fn = window.postJson || postJson;
  return fn("/api/panel/redlines", { before_text, after_text });
}
async function postCitationResolve({ findings, citations }) {
  const hasF = Array.isArray(findings) && findings.length > 0;
  const hasC = Array.isArray(citations) && citations.length > 0;
  if (hasF === hasC) throw new Error('Provide exactly one of findings or citations');
  const fn = window.postJson || postJson;
  return fn('/api/citation/resolve', hasF ? { findings } : { citations });
}
window.postCitationResolve = postCitationResolve;
export {
  postJson,
  apiAnalyze,
  apiGptDraft,
  apiHealth,
  apiQaRecheck,
  apiSummary,
  apiSummaryGet,
  apiSuggestEdits,
  postRedlines,
  postCitationResolve,
  applyMetaToBadges,
  metaFromResponse,
  parseFindings
};
