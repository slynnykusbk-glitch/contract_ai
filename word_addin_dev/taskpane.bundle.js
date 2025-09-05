// word_addin_dev/app/assets/api-client.ts
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
  const r = await fetch(base() + path, {
    method,
    headers: { "content-type": "application/json" },
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

// word_addin_dev/app/assets/notifier.ts
function notifyOk(msg) {
  try {
    console.log("[OK]", msg);
  } catch {
  }
}
function notifyErr(msg) {
  try {
    console.error("[ERR]", msg);
  } catch {
  }
}
function notifyWarn(msg) {
  try {
    console.warn("[WARN]", msg);
  } catch {
  }
}

// word_addin_dev/app/assets/office.ts
async function getWholeDocText() {
  return await Word.run(async (ctx) => {
    const body = ctx.document.body;
    body.load("text");
    await ctx.sync();
    return (body.text || "").trim();
  });
}

// word_addin_dev/app/assets/taskpane.ts
var Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};
function slot(id, role) {
  return document.querySelector(`[data-role="${role}"]`) || document.getElementById(id);
}
function renderResults(res) {
  const clause = slot("resClauseType", "clause-type");
  if (clause) clause.textContent = res?.clause_type || "\u2014";
  const findingsArr = Array.isArray(res?.findings) ? res.findings : [];
  const findingsList = slot("findingsList", "findings");
  if (findingsList) {
    findingsList.innerHTML = "";
    findingsArr.forEach((f) => {
      const li = document.createElement("li");
      li.textContent = typeof f === "string" ? f : JSON.stringify(f);
      findingsList.appendChild(li);
    });
  }
  const recoArr = Array.isArray(res?.recommendations) ? res.recommendations : [];
  const recoList = slot("recoList", "recommendations");
  if (recoList) {
    recoList.innerHTML = "";
    recoArr.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = typeof r === "string" ? r : JSON.stringify(r);
      recoList.appendChild(li);
    });
  }
  const count = slot("resFindingsCount", "findings-count");
  if (count) count.textContent = String(findingsArr.length);
  const pre = slot("rawJson", "raw-json");
  if (pre) pre.textContent = JSON.stringify(res ?? {}, null, 2);
}
function wireResultsToggle() {
  const toggle = slot("toggleRaw", "toggle-raw-json");
  const pre = slot("rawJson", "raw-json");
  if (toggle && pre) {
    pre.style.display = "none";
    toggle.addEventListener("click", () => {
      pre.style.display = pre.style.display === "none" ? "block" : "none";
    });
  }
}
function setConnBadge(ok) {
  const el = document.getElementById("connBadge");
  if (el) el.textContent = `Conn: ${ok === null ? "\u2014" : ok ? "\u2713" : "\xD7"}`;
}
function setOfficeBadge(txt) {
  const el = document.getElementById("officeBadge");
  if (el) el.textContent = `Office: ${txt ?? "\u2014"}`;
}
function $(sel) {
  return document.querySelector(sel);
}
function getSelectionAsync() {
  return new Promise((resolve, reject) => {
    try {
      Office.context.document.getSelectedDataAsync(Office.CoercionType.Text, (r) => {
        if (r.status === Office.AsyncResultStatus.Succeeded) {
          resolve((r.value || "").toString().trim());
        } else {
          reject(r.error);
        }
      });
    } catch (e) {
      reject(e);
    }
  });
}
async function getSelectionContext(chars = 200) {
  try {
    return await Word.run(async (ctx) => {
      const sel = ctx.document.getSelection();
      const body = ctx.document.body;
      sel.load("text");
      body.load("text");
      await ctx.sync();
      const full = body.text || "";
      const s = sel.text || "";
      const idx = full.indexOf(s);
      if (idx === -1) return { before: "", after: "" };
      return {
        before: full.slice(Math.max(0, idx - chars), idx),
        after: full.slice(idx + s.length, idx + s.length + chars)
      };
    });
  } catch (e) {
    console.warn("context fail", e);
    return { before: "", after: "" };
  }
}
async function onUseSelection() {
  try {
    const txt = await getSelectionAsync();
    const el = document.getElementById("originalClause");
    if (el) {
      el.value = txt;
      el.setAttribute("data-role", "source-loaded");
    }
  } catch (e) {
    notifyWarn("Failed to load selection");
    console.error(e);
  }
}
async function onUseWholeDoc() {
  try {
    const txt = await getWholeDocText();
    const el = document.getElementById("originalClause");
    if (el) {
      el.value = txt;
      el.setAttribute("data-role", "source-loaded");
    }
  } catch (e) {
    notifyWarn("Failed to load document");
    console.error(e);
  }
}
async function onGetAIDraft(ev) {
  try {
    const src = $(Q.original);
    const dst = $(Q.proposed);
    let text = (src?.value ?? "").trim();
    if (!text) {
      try {
        text = await getSelectionAsync();
        if (src) src.value = text;
      } catch {
      }
    }
    if (!text) {
      notifyWarn("No source text");
      return;
    }
    const modeSel = document.getElementById("cai-mode");
    const mode = modeSel?.value || "friendly";
    const ctx = await getSelectionContext(200);
    const { ok, json, resp } = await apiGptDraft(
      text,
      mode,
      { before_text: ctx.before, after_text: ctx.after }
    );
    if (!ok) {
      notifyWarn("Draft failed");
      return;
    }
    try {
      applyMetaToBadges(metaFromResponse(resp));
    } catch {
    }
    const proposed = (json?.proposed_text ?? "").toString();
    if (dst) {
      if (!dst.id) dst.id = "proposedText";
      if (!dst.name) dst.name = "proposed";
      dst.dataset.role = "proposed-text";
      dst.value = proposed;
      dst.dispatchEvent(new Event("input", { bubbles: true }));
      notifyOk("Draft ready");
    } else {
      notifyWarn("Proposed textarea not found");
    }
  } catch (e) {
    notifyWarn("Draft error");
    console.error(e);
  }
}
async function doHealth() {
  try {
    const { ok, json, resp } = await apiHealth();
    try {
      applyMetaToBadges(metaFromResponse(resp));
    } catch {
    }
    setConnBadge(ok);
    notifyOk(`Health: ${json.status} (schema ${json.schema})`);
  } catch (e) {
    setConnBadge(false);
    notifyWarn("Health failed");
    console.error(e);
  }
}
async function doAnalyzeDoc() {
  const text = await getWholeDocText();
  if (!text || !text.trim()) {
    notifyErr("\u0412 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435 \u043D\u0435\u0442 \u0442\u0435\u043A\u0441\u0442\u0430");
    return;
  }
  const { json, resp } = await apiAnalyze(text);
  try {
    applyMetaToBadges(metaFromResponse(resp));
  } catch {
  }
  renderResults(json);
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}
async function doQARecheck() {
  const text = await getWholeDocText();
  const { json, resp } = await apiQaRecheck(text, []);
  try {
    applyMetaToBadges(metaFromResponse(resp));
  } catch {
  }
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
  notifyOk("QA recheck OK");
}
function bindClick(sel, fn) {
  const el = document.querySelector(sel);
  if (!el) return;
  el.addEventListener("click", (e) => {
    e.preventDefault();
    fn();
  });
  el.classList.remove("js-disable-while-busy");
  el.removeAttribute("disabled");
}
async function onApplyTracked() {
  try {
    const dst = $(Q.proposed);
    const proposed = (dst?.value || "").trim();
    if (!proposed) {
      notifyWarn("No draft to insert");
      return;
    }
    await Word.run(async (ctx) => {
      let range = ctx.document.getSelection();
      ctx.document.trackRevisions = true;
      range.insertText(proposed, "Replace");
      try {
        range.insertComment("AI draft");
      } catch {
      }
      await ctx.sync();
    });
    notifyOk("Inserted into Word");
  } catch (e) {
    notifyWarn("Insert failed");
    console.error(e);
  }
}
async function onAcceptAll() {
  try {
    const dst = $(Q.proposed);
    const proposed = (dst?.value || "").trim();
    if (!proposed) {
      window.toast?.("Nothing to accept");
      return;
    }
    const cid = (document.getElementById("cid")?.textContent || "").trim();
    const base2 = (() => {
      try {
        return (localStorage.getItem("backendUrl") || "https://localhost:9443").replace(/\/+$/, "");
      } catch {
        return "https://localhost:9443";
      }
    })();
    const link = cid && cid !== "\u2014" ? `${base2}/api/trace/${cid}` : "AI draft";
    await Word.run(async (ctx) => {
      const range = ctx.document.getSelection();
      ctx.document.trackRevisions = true;
      range.insertText(proposed, "Replace");
      try {
        range.insertComment(link);
      } catch {
      }
      await ctx.sync();
    });
    window.toast?.("Accepted into Word");
    console.log("[OK] Accepted into Word");
  } catch (e) {
    window.toast?.("Accept failed");
    console.error(e);
  }
}
async function onRejectAll() {
  try {
    const dst = $(Q.proposed);
    if (dst) {
      dst.value = "";
      dst.dispatchEvent(new Event("input", { bubbles: true }));
    }
    await Word.run(async (ctx) => {
      const range = ctx.document.getSelection();
      const revs = range.revisions;
      revs.load("items");
      await ctx.sync();
      (revs.items || []).forEach((r) => {
        try {
          r.reject();
        } catch {
        }
      });
      await ctx.sync();
    });
    window.toast?.("Rejected");
    console.log("[OK] Rejected");
  } catch (e) {
    window.toast?.("Reject failed");
    console.error(e);
  }
}
function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyzeDoc", doAnalyzeDoc);
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
  bindClick("#btn-use-selection", onUseSelection);
  bindClick("#btn-use-whole", onUseWholeDoc);
  bindClick("#btnInsertIntoWord", onInsertIntoWord);
  bindClick("#btnApplyTracked", onApplyTracked);
  bindClick("#btnAcceptAll", onAcceptAll);
  bindClick("#btnRejectAll", onRejectAll);
  wireResultsToggle();
  console.log("Panel UI wired");
}
async function onInsertIntoWord() {
  try {
    const dst = $(Q.proposed);
    const txt = (dst?.value || "").trim();
    if (!txt) {
      notifyWarn("No draft to insert");
      return;
    }
    if (window.Office && window.Word) {
      await Word.run(async (ctx) => {
        const range = ctx.document.getSelection();
        range.insertText(txt, "Replace");
        await ctx.sync();
      });
      notifyOk("Inserted into Word");
    } else {
      await navigator.clipboard.writeText(txt);
      notifyWarn("Not in Office environment; result copied to clipboard");
    }
  } catch (e) {
    try {
      await navigator.clipboard.writeText($(Q.proposed)?.value || "");
    } catch {
    }
    notifyWarn("Not in Office environment; result copied to clipboard");
    console.error(e);
  }
}
async function bootstrap() {
  if (document.readyState === "loading") {
    await new Promise((res) => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
  }
  wireUI();
  try {
    await doHealth();
  } catch {
  }
  try {
    if (window.Office?.onReady) {
      const info = await window.Office.onReady();
      setOfficeBadge(`${info?.host || "Word"} \u2713`);
    }
  } catch {
    setOfficeBadge(null);
  }
}
// Codex added helpers for nth occurrence targeting
function normalizeText(s){return s.replace(/\r\n?/g,"\n").trim().replace(/[ \t]+/g," ");}
async function mapFindingToRange(f){const last=window.__lastAnalyzed||"";const snippet=normalizeText(f.snippet||"");const occIdx=(()=>{if(typeof f.start!=="number"||!snippet)return 0;let idx=-1,n=0;while((idx=last.indexOf(snippet,idx+1))!==-1&&idx<f.start)n++;return n;})();try{return await Word.run(async ctx=>{const body=ctx.document.body;const searchRes=body.search(snippet,{matchCase:false,matchWholeWord:false});searchRes.load("items");await ctx.sync();const items=searchRes.items||[];return items[Math.min(occIdx,Math.max(0,items.length-1))]||null;});}catch(e){console.warn("mapFindingToRange fail",e);return null;}}
async function annotateFindingsIntoWord(findings){const last=window.__lastAnalyzed||"";for(const f of findings){const snippet=normalizeText(f.snippet||"");const occIdx=(()=>{if(typeof f.start!=="number"||!snippet)return 0;let idx=-1,n=0;while((idx=last.indexOf(snippet,idx+1))!==-1&&idx<f.start)n++;return n;})();try{await Word.run(async ctx=>{const body=ctx.document.body;const searchRes=body.search(snippet,{matchCase:false,matchWholeWord:false});searchRes.load("items");await ctx.sync();const items=searchRes.items||[];const range=items[Math.min(occIdx,Math.max(0,items.length-1))];if(range){const msg=`${f.rule_id} (${f.severity})${f.advice?": "+f.advice:""}`;range.insertComment(msg);}await ctx.sync();});}catch(e){console.warn("annotate fail",e);}}}
async function applyOpsTracked(ops){if(!ops||!ops.length)return;const last=window.__lastAnalyzed||"";await Word.run(async ctx=>{const body=ctx.document.body;ctx.document.trackRevisions=true;for(const op of ops){const snippet=last.slice(op.start,op.end);const occIdx=(()=>{let idx=-1,n=0;while((idx=last.indexOf(snippet,idx+1))!==-1&&idx<op.start)n++;return n;})();const found=body.search(snippet,{matchCase:false,matchWholeWord:false});found.load("items");await ctx.sync();const items=found.items||[];const target=items[Math.min(occIdx,Math.max(0,items.length-1))];if(target){target.insertText(op.replacement,"Replace");try{target.insertComment("AI edit");}catch{}}else{console.warn("[applyOpsTracked] match not found",{snippet,occIdx});}await ctx.sync();}});}
bootstrap();
