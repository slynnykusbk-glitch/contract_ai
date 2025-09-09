// word_addin_dev/app/selftest.js - extracted module from panel_selftest.html
// Expected API schema version: 1.4

// ---------------------- helpers ----------------------
const LS_KEY = "panel:backendUrl";
const API_KEY_STORAGE = "api_key";
const SCHEMA_STORAGE = "schemaVersion";
const DRAFT_PATH = "/api/gpt-draft";
const SAMPLE = "Governing law: England and Wales.";
let clientCid = genCid();
let lastCid = ""; // from response headers

function showMeta(meta){
  const prov = document.getElementById("llmProv");
  const model = document.getElementById("llmModel");
  prov.textContent = (meta && meta.provider) || "—";
  model.textContent = (meta && meta.model) || "—";
  const modeEl = document.getElementById("llmLatency");
  if (modeEl && meta && meta.mode) {
    modeEl.textContent = meta.mode;
    modeEl.className = meta.mode === "mock" ? "ok" : "";
  }
  const badge = document.getElementById("llmBadge");
  if (badge) badge.style.display = (meta && meta.mode === "mock") ? "inline-block" : "none";
}

function pickDocType(summary) {
  summary = summary || {};
  let list = [];
  if (Array.isArray(summary.doc_types)) list = summary.doc_types;
  else if (summary.document && Array.isArray(summary.document.doc_types)) list = summary.document.doc_types;
  // legacy: summary.doc_type = { top:{type,score}, confidence, candidates[] }
  if (!list.length && summary.doc_type && (summary.doc_type.top || summary.doc_type.candidates)) {
    const top = summary.doc_type.top || {};
    const conf = (typeof summary.doc_type.confidence === 'number')
      ? summary.doc_type.confidence
      : (typeof top.score === 'number' ? top.score : null);
    return { name: top.type || top.name || null, confidence: conf };
  }
  let best = null;
  if (list && list.length) {
    best = list.reduce((acc, cur) => {
      const c = typeof cur.confidence === 'number' ? cur.confidence : (typeof cur.score === 'number' ? cur.score : 0);
      const n = cur.name || cur.type || cur.slug || cur.id || null;
      if (!acc || c > acc.confidence) return { name: n, confidence: c };
      return acc;
    }, null);
  } else {
    let n2 = summary.type || (summary.document && summary.document.type) || null;
    let c2 = summary.type_confidence;
    if (c2 == null && summary.document && summary.document.type_confidence != null) c2 = summary.document.type_confidence;
    if (typeof c2 === 'string') { const f = parseFloat(c2); c2 = isNaN(f) ? null : f; }
    best = { name: n2, confidence: c2 };
  }
  return best || { name: null, confidence: null };
}

function genCid(){ return "cid-" + Math.random().toString(16).slice(2) + "-" + Date.now().toString(16); }

function normBase(u){
  if (!u) return "";
  let s = String(u).trim();
  if (s.startsWith("//")) s = "https:" + s;
  if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(s)) s = "https://" + s;
  s = s.replace(/^http:\/\/(127\.0\.0\.1|localhost)(:9443)(\/|$)/, "https://$1$2$3");
  return s.replace(/\/+$/, "");
}
function joinUrl(base, path){
  if (!base) throw new Error("backend base URL is empty");
  if (!path.startsWith("/")) path = "/" + path;
  return base.replace(/\/+$/, "") + path;
}
function saveBase(){ try{ const v=document.getElementById("backendInput").value.trim(); localStorage.setItem(LS_KEY, v); localStorage.setItem("backendUrl", v); }catch{} }
function loadBase(){
  let v = localStorage.getItem(LS_KEY) || document.getElementById("backendInput").value || "https://localhost:9443";
  v = normBase(v);
  document.getElementById("backendInput").value = v || "https://localhost:9443";
  try{ localStorage.setItem("backendUrl", v); }catch{}
  return v;
}

function saveApiKey(){
  try{ const v=document.getElementById("apiKeyInput").value.trim(); localStorage.setItem(API_KEY_STORAGE, v);}catch{}
}
function loadApiKey(){
  let v="";
  try{ v = localStorage.getItem(API_KEY_STORAGE) || ""; }catch{}
  const el = document.getElementById("apiKeyInput");
  if(el) el.value = v;
  return v;
}
function saveSchemaVersion(){
  try{
    const v=document.getElementById("schemaInput").value.trim();
    localStorage.setItem(SCHEMA_STORAGE, v);
    CAI.Store?.setSchemaVersion?.(v);
  }catch{}
}
function loadSchemaVersion(){
  let v="";
  try{ v = localStorage.getItem(SCHEMA_STORAGE) || ""; }catch{}
  const el = document.getElementById("schemaInput");
  if(el) el.value = v;
  try{ CAI.Store?.setSchemaVersion?.(v); }catch{}
  return v;
}
function setCidLabels(){
  document.getElementById("cidLbl").textContent = clientCid;
  document.getElementById("lastCidLbl").textContent = lastCid || "(none yet)";
}
function setJSON(elId, obj){
  const el = document.getElementById(elId);
  try { el.textContent = JSON.stringify(obj, null, 2); }
  catch { el.textContent = String(obj); }
}
function setStatusRow(rowId, {code, xcid, xcache, xschema, latencyMs, ok, error_code, detail}){
  const tr = document.getElementById(rowId);
  const cells = tr.getElementsByTagName('td');
  const latencyText = (latencyMs != null ? `${latencyMs} ms` : (xcid ? "" : ""));
  cells[1].textContent = code ?? "";
  cells[2].textContent = xcid ?? "";
  cells[3].textContent = xcache ?? "";
  cells[4].textContent = xschema ?? "";
  cells[5].textContent = latencyText;
  if (ok) {
    cells[6].innerHTML = '<span class="ok">ok</span>';
  } else {
    const msg = error_code ? `${error_code}${detail ? ': ' + detail : ''}` : 'error';
    cells[6].innerHTML = `<span class="err">${msg}</span>`;
  }
}

function showResp(r){
  const el = document.getElementById("resp");
  if(!r.ok){
    try{ el.textContent = `HTTP ${r.code}\n` + JSON.stringify(r.body, null, 2); }
    catch{ el.textContent = `HTTP ${r.code}`; }
    return;
  }
  if(r.body && r.body.status && r.body.status !== "ok"){
    el.textContent = `API error: ${r.body.detail || r.body.error_code || ''}`;
    return;
  }
  setJSON("resp", r.body);
}

function onClick(id, handler){
  var el = document.getElementById(id);
  if (!el) return;
  el.addEventListener('click', handler);
}

async function fetchJSON(path){
  const base = normBase(document.getElementById("backendInput").value);
  const url = joinUrl(base, path);
  const resp = await fetch(url, { method:"GET" });
  return await resp.json();
}

async function loadOpenAPI(){
  try{
    const spec = await fetchJSON('/openapi.json');
    return spec.paths || {};
  }catch{
    return {};
  }
}

const TESTS = [];

function buildRowsFromOpenAPI(paths){
  const btns = document.getElementById('testsBtns');
  const tbody = document.getElementById('statusBody');
  if(!btns || !tbody) return;
  const slugMap = {
    '/health':'health',
    '/api/analyze':'analyze',
    '/api/summary':'summary',
    '/api/gpt-draft':'draft',
    '/api/suggest_edits':'suggest',
    '/api/qa-recheck':'qa',
    '/api/calloff/validate':'calloff',
    '/api/trace/{cid}':'trace',
    '/api/citation/resolve':'citation-resolve'
  };
  const labelMap = {
    '/api/citation/resolve':'Resolve citations'
  };
  const special = {
    '/health': testHealth,
    '/api/analyze': testAnalyze,
    '/api/summary': testSummary,
    '/api/gpt-draft': testDraft,
    '/api/suggest_edits': testSuggest,
    '/api/qa-recheck': testQA,
    '/api/calloff/validate': testCalloff,
    '/api/trace/{cid}': testTrace,
    '/api/citation/resolve': testCitationResolve
  };
  for (const [p, methods] of Object.entries(paths)){
    if(!p.startsWith('/api/') && p !== '/health') continue;
    for (const m of Object.keys(methods)){
      const method = m.toUpperCase();
      if(method !== 'GET' && method !== 'POST') continue;
      const slug = slugMap[p] || p.replace(/^\/api\//,'').replace(/[{}]/g,'').replace(/\//g,'-');
      const rowId = `row-${slug}`;
      const btnId = `btn-${slug}`;
      const label = labelMap[p] || `${method} ${p}`;
      btns.insertAdjacentHTML('beforeend', `<button id="${btnId}">${label}</button>`);
      const rowHtml = `<tr id="${rowId}"><td>${label}</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>`;
      tbody.insertAdjacentHTML('beforeend', rowHtml);
      const fn = special[p] || (() => runGeneric({method, path:p, rowId}));
      onClick(btnId, fn);
      TESTS.push({rowId, fn});
    }
  }
}

async function callEndpoint({name, method, path, body, dynamicPathFn}) {
  const base = normBase(document.getElementById("backendInput").value);
  if (!base) { console.log("Please enter backend URL"); return { error:true }; }

  const origBase1 = localStorage.getItem(LS_KEY);
  const origBase2 = localStorage.getItem("backendUrl");
  try {
    localStorage.setItem(LS_KEY, base);
    localStorage.setItem("backendUrl", base);
  } catch {}

  const origKey = localStorage.getItem(API_KEY_STORAGE);
  const origSchema = localStorage.getItem(SCHEMA_STORAGE);
  if (path !== "/health") {
    try {
      const k = document.getElementById("apiKeyInput").value.trim();
      const s = document.getElementById("schemaInput").value.trim();
      if (!k || !s) {
        alert("Please enter API Key (x-api-key) and Schema Version (x-schema-version)");
        return { ok:false, error_code:"CLIENT", detail:"Missing headers" };
      }
      localStorage.setItem(API_KEY_STORAGE, k);
      localStorage.setItem(SCHEMA_STORAGE, s);
      CAI.Store?.setApiKey?.(k);
      CAI.Store?.setSchemaVersion?.(s);
    } catch {}
  }

  let r;
  const rel = dynamicPathFn ? dynamicPathFn() : path;
  if (method === "GET") {
    const url = joinUrl(base, rel);
    const http = await fetch(url, { method:"GET" });
    const json = await http.json().catch(() => ({}));
    r = { http, json, headers: http.headers };
  } else if (method === "POST") {
    r = await postJson(rel, body || {});
  } else {
    return { ok:false, error_code:"CLIENT", detail:"Unsupported method" };
  }

  if (origBase1 == null) { localStorage.removeItem(LS_KEY); } else { localStorage.setItem(LS_KEY, origBase1); }
  if (origBase2 == null) { localStorage.removeItem("backendUrl"); } else { localStorage.setItem("backendUrl", origBase2); }
  if (path !== "/health") {
    if (origKey == null) { localStorage.removeItem(API_KEY_STORAGE); } else { localStorage.setItem(API_KEY_STORAGE, origKey); }
    if (origSchema == null) { localStorage.removeItem(SCHEMA_STORAGE); } else { localStorage.setItem(SCHEMA_STORAGE, origSchema); }
  }

  const hdr = r.headers || { get: () => "" };
  const cid = hdr.get("x-cid") || "";
  const cache = hdr.get("x-cache") || "";
  const schema = hdr.get("x-schema-version") || "";
  const latency = Number(hdr.get("x-latency-ms")) || null;
  if (cid) lastCid = cid;
  if (schema) { try { CAI.Store?.setSchemaVersion?.(schema); } catch {} }
  setCidLabels();
  const ok = r.http ? (r.http.ok && r.json && r.json.status === "ok") : false;
  return {
    url: path,
    code: r.http ? r.http.status : null,
    body: r.json,
    xcid: cid,
    xcache: cache,
    xschema: schema,
    latencyMs: latency,
    ok,
    error_code: r.json && r.json.error_code ? r.json.error_code : "",
    detail: r.json && r.json.detail ? r.json.detail : ""
  };
}

function resolveDynamicPath(p){
  return p.includes('{cid}') ? p.replace('{cid}', encodeURIComponent(lastCid || clientCid || '')) : p;
}

async function runGeneric({method, path, rowId}){
  const r = await callEndpoint({ name:path, method, path, dynamicPathFn: () => resolveDynamicPath(path) });
  setStatusRow(rowId, r);
  if(path.includes('/trace')) setJSON('trace', r.body); else showResp(r);
  showMeta(r.body && (r.body.meta || r.body.llm || {}));
  return r;
}

async function pingLLM(){
  const latEl = document.getElementById("llmLatency");
  latEl.textContent = "…";
  latEl.className = "";
  try {
    const resp = await CAI.API.get("/api/llm/ping");
    const meta = resp.meta || resp.json.llm || {};
    if (meta.provider || meta.model || meta.mode) showMeta(meta);
    const ms = meta.latencyMs || Number(resp.resp.headers?.get("x-latency-ms")) || 0;
    latEl.textContent = ms + "ms";
    latEl.className = resp.ok ? "ok" : "err";
    showResp({ ok: resp.ok, code: resp.resp.status, body: resp.json });
  } catch (e) {
    latEl.textContent = "ERR";
    latEl.className = "err";
  }
}

// ---------------------- individual tests ----------------------
async function testHealth(){
  const r = await callEndpoint({ name:"health", method:"GET", path:"/health" });
  setStatusRow("row-health", r);
  showResp(r);
  if (r.body) {
    showMeta(r.body.meta || r.body.llm || {});
  }
  return r;
}
function getSampleText(){
  return SAMPLE;
}

async function testAnalyze(){
  const r = await callEndpoint({
    name:"analyze", method:"POST", path:"/api/analyze",
    body:{ text: SAMPLE }
  });
  setStatusRow("row-analyze", r);
  showResp(r);
  showMeta(r.body && r.body.meta || {});
  return r;
}
async function testSummary(){
  const r = await callEndpoint({
    name:"summary", method:"POST", path:"/api/summary",
    body:{ text: SAMPLE }
  });
  setStatusRow("row-summary", r);
  if(!r.ok || (r.body && r.body.status !== "ok")){
    showResp(r);
    return r;
  }
  const el = document.getElementById("resp");
  try {
    const s = JSON.stringify(r.body, null, 2)
      .replace(/"schema_version"\s*:\s*"([^"]+)"/,'<span class="ok">"schema_version": "$1"</span>')
      .replace(/"type"\s*:\s*"([^"]+)"/,'<span class="ok">"type": "$1"</span>')
      .replace(/"has_cap"\s*:\s*(true|false)/,'<span class="ok">"has_cap": $1</span>')
      .replace(/"has_conditions"\s*:\s*(true|false)/,'<span class="ok">"has_conditions": $1</span>')
      .replace(/"has_warranties"\s*:\s*(true|false)/,'<span class="ok">"has_warranties": $1</span>');
    el.innerHTML = s;
  } catch {
    setJSON("resp", r.body);
  }
  const snapEl = document.getElementById("docSnap");
  const summary = r.body && (r.body.summary || r.body) || null;
  const docType = pickDocType(summary || {});
  const typeEl = document.querySelector('[data-snap-type]');
  const confEl = document.querySelector('[data-snap-type-confidence]');
  if (typeEl) typeEl.textContent = docType.name ?? '—';
  if (confEl) confEl.textContent =
    docType.confidence != null ? Math.round(docType.confidence * 100) + '%' : '—';
  if (summary) {
    try { snapEl.textContent = JSON.stringify(summary, null, 2); }
    catch { snapEl.textContent = String(summary); }
  } else {
    snapEl.textContent = "";
  }
  return r;
}

async function testDraft(){
  const r = await callEndpoint({
    name:"draft", method:"POST", path:DRAFT_PATH,
    body:{ text: SAMPLE }
  });
  const ok = r.ok && r.body && r.body.status === "ok";
  setStatusRow("row-draft", Object.assign({}, r, { ok: !!ok }));
  showResp(r);
  showMeta(r.body && r.body.meta || {});
  const badge = document.getElementById("llmBadge");
  const meta = r.body && r.body.meta ? r.body.meta : {};
  if (meta.mode === "mock") { badge.style.display = "inline-block"; } else { badge.style.display = "none"; }
  return r;
}
async function testSuggest(){
  const r = await callEndpoint({
    name:"suggest", method:"POST", path:"/api/suggest_edits",
    body:{ text: SAMPLE, clause_type: "termination" }
  });
  setStatusRow("row-suggest", r);
  showResp(r);
  showMeta(r.body && r.body.meta || {});
  return r;
}
async function testQA(){
  const r = await callEndpoint({
    name:"qa", method:"POST", path:"/api/qa-recheck",
    body:{ text: SAMPLE, applied_changes:[] }
  });
  setStatusRow("row-qa", r);
  showResp(r);
  showMeta(r.body && r.body.meta || {});
  return r;
}
async function testCitationResolve(){
  const fn = window.postCitationResolve || postCitationResolve;
  const { http, json, headers } = await fn({ citations:[{ instrument: 'Act', section: '1' }] });
  const meta = metaFromResponse({ headers, json, status: http.status });
  setStatusRow('row-citation-resolve', {
    code: http.status,
    xcid: meta.cid,
    xcache: meta.xcache,
    xschema: meta.schema,
    latencyMs: meta.latencyMs,
    ok: http.ok
  });
  showResp({ ok: http.ok, code: http.status, body: json });
  showMeta(json && (json.meta || json.llm || {}));
  return { http, json, headers };
}
async function testCalloff(){
  const r = await callEndpoint({
    name:"calloff", method:"POST", path:"/api/calloff/validate",
    body:{
      term:"",
      description:"[●]",
      price:"",
      currency:"",
      vat:"",
      delivery_point:"",
      representatives:"",
      notices:"",
      po_number:""
    }
  });
  setStatusRow("row-calloff", r);
  if(!r.ok || (r.body && r.body.status !== "ok")){
    showResp(r);
    return r;
  }
  const issues = (r.body && r.body.issues) ? r.body.issues.length : 0;
  const tr = document.getElementById("row-calloff");
  const cells = tr.getElementsByTagName('td');
  cells[6].innerHTML = r.ok ? `<span class="ok">ok / issues ${issues}</span>` : '<span class="err">error</span>';
  setJSON("resp", r.body);
  return r;
}
async function testTrace(){
  const cid = lastCid || clientCid || "cid-dummy";
  const r = await callEndpoint({
    name:"trace", method:"GET",
    dynamicPathFn: () => `/api/trace/${encodeURIComponent(cid)}`
  });
  setStatusRow("row-trace", r);
  setJSON("trace", r.body);
  return r;
}

async function runAll(){
  const apiKey = document.getElementById("apiKeyInput")?.value.trim();
  const schema = document.getElementById("schemaInput")?.value.trim();
  if (!apiKey || !schema) {
    alert("Please enter API Key (x-api-key) and Schema Version (x-schema-version)");
    return;
  }
  saveApiKey();
  saveSchemaVersion();
  for (const t of TESTS) {
    setStatusRow(t.rowId, {code:"",xcid:"",xcache:"",xschema:"",latencyMs:null,ok:false});
  }
  document.getElementById("resp").textContent = "";
  document.getElementById("docSnap").textContent = "";
  document.getElementById("trace").textContent = "";
  clientCid = genCid();
  setCidLabels();
  for (const t of TESTS) {
    await t.fn();
  }
}

// ---------------------- init & events ----------------------
onClick("saveBtn", () => { saveBase(); console.log("Saved"); });
onClick("runAllBtn", runAll);
onClick("pingBtn", pingLLM);
onClick("saveKeyBtn", () => { saveApiKey(); saveSchemaVersion(); console.log("Saved headers"); });

// Load defaults on first paint
window.addEventListener("DOMContentLoaded", async () => {
  loadBase();
  loadApiKey();
  const storedSchema = loadSchemaVersion();
  setCidLabels();
  const paths = await loadOpenAPI();
  buildRowsFromOpenAPI(paths);
  try {
    const resp = await CAI.API.get('/health');
    const llm = (resp && resp.json && resp.json.llm) || {};
    const model = (llm.models && llm.models.draft) || llm.model;
    showMeta({ provider: llm.provider, model, mode: llm.mode });

    const serverSchema =
      (resp.headers && resp.headers.get && resp.headers.get('x-schema-version')) ||
      (resp.json && resp.json.schema) || '';
    if (serverSchema && storedSchema !== serverSchema) {
      const el = document.getElementById('schemaInput');
      if (el) el.value = serverSchema;
      try {
        localStorage.setItem(SCHEMA_STORAGE, serverSchema);
        CAI.Store?.setSchemaVersion?.(serverSchema);
      } catch {}
      const warnEl = document.getElementById('schemaWarn');
      if (warnEl && storedSchema) {
        warnEl.textContent = `Schema mismatch: ${storedSchema} → ${serverSchema}`;
        warnEl.style.display = 'inline';
      }
    }
  } catch {
    const latEl = document.getElementById('llmLatency');
    if (latEl) { latEl.textContent = 'ERR'; latEl.className = 'err'; }
  }
});
