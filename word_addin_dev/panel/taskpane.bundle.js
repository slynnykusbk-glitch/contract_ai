console.info("[PANEL] Build:", "dev-"+Date.now());

// import { API } from "./assets/api-client.js";
import { API } from "./assets/api-client.js";

const backendInput = document.getElementById("backendInput");
if (backendInput) backendInput.value = localStorage.getItem("backendUrl") || "https://localhost:9443";

document.getElementById("btnSave")?.addEventListener("click", () => {
  const v = backendInput.value.trim();
  if (v) localStorage.setItem("backendUrl", v);
});

function getOriginalClauseText(){
  return document.getElementById("originalClause")?.value || "";
}
function getRiskMode(){
  return document.getElementById("riskThreshold")?.value || "live";
}
function getDraftMode(){
  return document.getElementById("cai-mode")?.value || "friendly";
}
function toast(msg){ console.log(msg); }

function setMeta(k,v){
  const ids={cid:"cidBadge",xcache:"xcacheBadge",latency:"latencyBadge",schema:"schemaBadge",provider:"providerBadge",model:"modelBadge",mode:"modeBadge"};
  const el=document.getElementById(ids[k]);
  if(el) el.textContent=v;
}
function setSnapshot(d){
  const t=document.querySelector('[data-snap-type]');
  const c=document.querySelector('[data-snap-type-confidence]');
  if(t) t.textContent=d.type;
  if(c) c.textContent=d.findingsCount ?? d.issuesCount ?? "";
}
function fillFindingsList(list){
  const ul=document.getElementById("findingsList");
  if(!ul) return;
  ul.innerHTML="";
  list.forEach(f=>{const li=document.createElement("li");li.textContent=f.message||JSON.stringify(f);ul.appendChild(li);});
}
function fillRecommendationsList(list){
  const ul=document.getElementById("recommendationsList");
  if(!ul) return;
  ul.innerHTML="";
  list.forEach(f=>{const li=document.createElement("li");li.textContent=f.message||JSON.stringify(f);ul.appendChild(li);});
}
function renderSummary(text){ const el=document.getElementById("summaryBox"); if(el) el.textContent=text; }
function setProposedText(text){ const el=document.getElementById("draftBox"); if(el) el.value=text; }
function applySuggestions(data){ console.log("applySuggestions", data); }

function renderMeta(r){
  setMeta("cid", r.headers.cid || "—");
  setMeta("xcache", r.headers.cache || "—");
  setMeta("latency", r.headers.latency || "—");
  setMeta("schema", r.headers.schema || "—");
  setMeta("provider", r.headers.provider || "—");
  setMeta("model", r.headers.model || "—");
  setMeta("mode", r.headers.mode || "—");
}

function renderFindings(analysis){
  setSnapshot({
    type: analysis?.clause_type || "unknown",
    findingsCount: (analysis?.findings || []).length,
    issuesCount: (analysis?.issues || []).length
  });
  fillFindingsList(analysis?.findings || []);
  fillRecommendationsList(analysis?.issues || []);
}

function renderApiError(what, r){
  console.warn(`[${what}] API error`, r);
  toast(`✖ ${what} error: http ${r.http}`);
}

function clearStorageAndReload(){
  try{ localStorage.clear(); }catch{}
  if(window.caches){ caches.keys().then(keys=>keys.forEach(k=>caches.delete(k))); }
  location.reload();
}

async function doHealth(){
  const r = await API.health();
  renderMeta(r);
  toast(r.ok ? "Conn: 200" : `Conn error: http ${r.http}`);
}

async function doAnalyzeDoc(){
  const text = getOriginalClauseText();
  if(!text?.trim()) return toast("⚠️ Paste or copy text first.");
  const r = await API.analyze(text, getRiskMode());
  renderMeta(r);
  if(r.ok){ renderFindings(r.data.analysis); }
  else { renderApiError("Analyze", r); }
}

async function doSummary(){
  const text = getOriginalClauseText();
  if(!text?.trim()) return toast("⚠️ Paste or copy text first.");
  const r = await API.summary(text);
  renderMeta(r);
  if(r.ok) renderSummary(r.data.summary);
  else renderApiError("Summary", r);
}

async function doGptDraft(){
  const text = getOriginalClauseText();
  if(!text?.trim()) return toast("⚠️ Paste or copy text first.");
  const r = await API.gptDraft(text, getDraftMode());
  renderMeta(r);
  if(r.ok) setProposedText(r.data.proposed_text || "");
  else renderApiError("GPT draft", r);
}

async function doSuggest(){
  const text = getOriginalClauseText();
  if(!text?.trim()) return toast("⚠️ Analyze first.");
  const r = await API.suggest(text, getDraftMode());
  renderMeta(r);
  if(r.ok) applySuggestions(r.data);
  else renderApiError("Suggest", r);
}

document.getElementById("btnTest")?.addEventListener("click", doHealth);
document.getElementById("analyzeBtn")?.addEventListener("click", doAnalyzeDoc);
document.getElementById("btnAnalyzeDoc")?.addEventListener("click", doAnalyzeDoc);
document.getElementById("btnSummary")?.addEventListener("click", doSummary);
document.getElementById("draftBtn")?.addEventListener("click", doGptDraft);
document.getElementById("btnSuggest")?.addEventListener("click", doSuggest);
document.getElementById("btnClearStorage")?.addEventListener("click", clearStorageAndReload);
