(function () {
  if (window.__CAI_WIRED__ === true) return;
  window.__CAI_WIRED__ = true;

  (function initBuild() {
    try {
      var u = new URL(window.location.href);
      var v = u.searchParams.get("v");
      if (v) window.__BUILD_ID__ = v;
    } catch (_) {}
    if (!window.__BUILD_ID__) {
      try {
        window.__BUILD_ID__ = "dev-" + Date.now();
      } catch (_) {
        window.__BUILD_ID__ = "dev";
      }
    }
  })();

  var BUILD = window.__BUILD_ID__;

  (function initClientCid() {
    function randHex(n) {
      var s = "";
      if (window.crypto && window.crypto.getRandomValues) {
        var a = new Uint8Array(n);
        window.crypto.getRandomValues(a);
        for (var i = 0; i < a.length; i++) s += ("0" + a[i].toString(16)).slice(-2);
      } else {
        for (var j = 0; j < n; j++) s += Math.floor(Math.random() * 256).toString(16).padStart(2, "0");
      }
      return s;
    }
    if (!window.__CLIENT_CID__) {
      window.__CLIENT_CID__ = "cid-" + randHex(8) + "-" + Date.now().toString(16);
    }
  })();

  var els = {};
  var CAI_STORE = window.CAI_STORE || (window.CAI_STORE = {
    settings: { riskThreshold: "high" },
    status: { cid: null, xcache: null, latencyMs: null, schemaVersion: null },
    analysis: { analysis: null, results: null, clauses: [], document: null }
  });
  window.LAST_DRAFT = window.LAST_DRAFT || "";

  var DRAFT_PATH = "/api/gpt-draft";

  var state = {
    cid: null,
    docText: "",
    clauseText: "",
    proposedText: "",
    analysis: null,
    draftResp: null
  };

var REQ_LOG = [];

  let __lastCopiedWhole = false;
  function lastCopiedWasWhole(){ return __lastCopiedWhole; }
  function setOriginalText(t){
    setVal(els.clause, t);
    state.clauseText = t;
  }
  function getDraftText(){
    const t = document.getElementById("draftText");
    return (t && t.value) ? t.value : "";
  }

  function $(id) { return document.getElementById(id); }
  function val(e) { return e ? (e.value || "") : ""; }
  function setVal(e, v) {
    if (!e) return;
    if (v && typeof v === "object") {
      v = v.draft_text || JSON.stringify(v, null, 2);
    }
    e.value = (v == null ? "" : String(v));
  }
  function txt(e, v) { if (e) e.textContent = (v == null ? "" : String(v)); }
  function esc(s) { return (s == null ? "" : String(s)).replace(/[&<>]/g, function(c){return c==="&"?"&amp;":c==="<"?"&lt;":"&gt;";}); }
  function en(e, on) { if (e) e.disabled = !on; }
  function log(s) {
    try {
      var n = els.console; if (!n) return;
      n.appendChild(document.createTextNode(String(s) + "\n"));
      n.scrollTop = n.scrollHeight;
    } catch (_) {}
  }
  function status(s) { log("[STATUS] " + s); }

  function setText(id, v){ var el=document.getElementById(id); if(el) el.textContent=(v==null?"":String(v)); }
  function getText(id){ var el=document.getElementById(id); return el?el.textContent:""; }
  function byId(id){ return document.getElementById(id); }
  function escapeHtml(s){ return esc(s); }

  function getOriginalClauseText(){ return getPanelTextOrFetch(); }
  function getRiskMode(){ return getModeOrDefault(); }
  function getDraftMode(){ return getModeOrDefault(); }

  // ---- Schema 1.3 mappers
  function mapAnalysis(resp) {
    const a = resp && resp.data && resp.data.analysis || null;
    if (!a) return { ok:false, reason:"no-analysis" };
    return {
      ok: true,
      clause_type: a.clause_type || "unknown",
      findings: Array.isArray(a.findings) ? a.findings : [],
      recommendations: Array.isArray(a.recommendations) ? a.recommendations : [],
      issues: Array.isArray(a.issues) ? a.issues : [],
      raw: a
    };
  }
  function mapDraft(resp) {
    const d = resp && resp.data || {};
    return {
      ok: !!(resp && resp.ok),
      proposed: d.proposed_text || d.after_text || "",
      before: d.before_text || "",
      after:  d.after_text  || "",
      diff:   (d.diff && d.diff.value) ? d.diff.value : ""
    };
  }

  // ---- Comment utilities
  CAI.buildCommentText = function(f, meta){
    const cid = meta && meta.cid ? meta.cid : "n/a";
    const rule = f && (f.rule_id || f.ruleId || "n/a");
    const sev = f && f.severity || "n/a";
    const title = f && (f.title || f.rule_id || f.ruleId || "" );
    const msg = f && (f.message || f.advice || "");
    const rec = f && (f.recommendation || "-");
    return `[CAI][cid:${cid}][rule:${rule}][sev:${sev}]\n${title}\n${msg}\nRecommendation: ${rec}`;
  };

  CAI.addCommentForFinding = function(ctx, body, finding, meta){
    const opts = { matchCase:false, matchWholeWord:false, ignorePunct:true, ignoreSpace:true };
    const snippet = finding.snippet || finding.excerpt || "";
    const words = String(finding.advice || "").toLowerCase().match(/[a-z0-9]+/gi) || [];
    const fallback = words.filter(w => w.length >= 3).slice(0,3).join(" ");
    const r1 = snippet ? body.search(snippet, opts) : null;
    if (r1) r1.load("items");
    const r2 = fallback ? body.search(fallback, opts) : null;
    if (r2) r2.load("items");
    if (!meta.queue) meta.queue = [];
    meta.queue.push({ finding, r1, r2 });
  };

  CAI.commentAllFindings = async function(findings, headers){
    const cid = headers && (headers['x-cid'] || headers['cid']) || (CAI.Store.get().meta && CAI.Store.get().meta.cid) || 'n/a';
    if (!Array.isArray(findings) || findings.length === 0) return;
    const meta = { cid, queue: [] };
    try {
      await Word.run(async ctx => {
        const comments = ctx.document.comments;
        comments.load("items/text");
        const body = ctx.document.body;
        for (const f of findings){
          CAI.addCommentForFinding(ctx, body, f, meta);
        }
        await ctx.sync();
        const existing = comments.items.map(c => c.text);
        for (const item of meta.queue){
          const f = item.finding;
          const prefix = `[CAI][cid:${cid}][rule:${f.rule_id}]`;
          if (existing.some(t => t.startsWith(prefix))) continue;
          let range = null;
          if (item.r1 && item.r1.items.length > 0) range = item.r1.items[0];
          else if (item.r2 && item.r2.items.length > 0) range = item.r2.items[0];
          if (!range) continue;
          range.insertComment(CAI.buildCommentText(f, meta));
        }
        await ctx.sync();
      });
    } catch(e){
      try { toast('⚠️ Failed to add comments'); } catch(_) {}
      console.warn('CAI.commentAllFindings', cid, e);
    }
  };

  // ---- Meta badges render
  function renderMeta() {
    const m = CAI.Store.get().meta;
    setText("cidBadge", m.cid || "—");
    setText("xcacheBadge", m.cache || "—");
    setText("latencyBadge", String(m.latencyMs || "—"));
    setText("schemaBadge", m.schema || "—");
    setText("providerBadge", m.provider || "—");
    setText("modelBadge", m.model || "—");
    setText("modeBadge", m.llm_mode || "—");
  }

  // при старте UI
  const backendInput = document.getElementById("backendUrl");
  if (backendInput) {
    backendInput.value = (window.CAI?.Store?.get()?.baseUrl) || "https://localhost:9443";
    backendInput.addEventListener("change", function(e){ CAI.Store.setBase(e.target.value); });
  }
  const riskSel = document.getElementById("riskSelect");
  if (riskSel) {
    riskSel.value = CAI.Store.get().risk || "medium";
    riskSel.addEventListener("change", function(e){ CAI.Store.setRisk(e.target.value); });
  }

  // LS keys (canonical + legacy fallback)
  var LS_KEY = "panel:backendUrl";
  var LS_KEY_OLD = "contract_ai_backend";

  function readLS(k) { try { return localStorage.getItem(k) || ""; } catch (_) { return ""; } }
  function writeLS(k, v) { try { localStorage.setItem(k, v); return true; } catch (_) { return false; } }

  function getModeOrDefault() {
    return (els.sugMode && val(els.sugMode)) || "friendly";
  }

  function getThresholdOrDefault() {
    return (val(els.riskThreshold) || CAI_STORE.settings.riskThreshold || "high").toLowerCase();
  }

  function toast(msg) {
    try { if (window.OfficeRuntime && OfficeRuntime.displayToastAsync) { OfficeRuntime.displayToastAsync(String(msg)); return; } }
    catch (_) {}
    try { alert(String(msg)); } catch (_) {}
    status(msg);
  }

  function showErr(msg) { toast(msg); }

  function simpleDiff(a, b) {
    const A = a.match(/\S+|\s+/g) || [];
    const B = b.match(/\S+|\s+/g) || [];
    const dp = Array(A.length + 1).fill(null).map(() => Array(B.length + 1).fill(0));
    for (let i = 1; i <= A.length; i++) for (let j = 1; j <= B.length; j++) dp[i][j] = A[i - 1] === B[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    let i = A.length, j = B.length, parts = [];
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && A[i - 1] === B[j - 1]) { parts.push({ type: "eq", text: A[i - 1] }); i--; j--; }
      else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) { parts.push({ type: "ins", text: B[j - 1] }); j--; }
      else { parts.push({ type: "del", text: A[i - 1] }); i--; }
    }
    return parts.reverse();
  }

  function renderDiff(orig, prop) {
    const parts = simpleDiff(orig, prop);
    const frag = parts.map(p => {
      if (p.type === "eq") return p.text.replace(/</g, "&lt;");
      if (p.type === "ins") return `<ins>${p.text.replace(/</g, "&lt;")}</ins>`;
      return `<del>${p.text.replace(/</g, "&lt;")}</del>`;
    }).join("");
    var el = document.getElementById("diffView");
    if (el) el.innerHTML = frag;
  }

  async function getPanelTextOrFetch() {
    var t = (val(els.clause) || "").trim();
    if (t) return t;
    var sel = await getSelectionText();
    if (sel) return sel;
    var doc = await getWholeDocText();
    return doc;
  }

  // HTTPS-only base normalization (no mixed content)
  function normBase(u) {
    if (!u) return "";
    var s = String(u).trim();
    // support protocol-relative //host:port
    if (s.startsWith("//")) s = "https:" + s;
    // if schema missing → force https://
    if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(s)) s = "https://" + s;
    // special case: http://127.0.0.1:9443 or http://localhost:9443 → force https
    s = s.replace(/^http:\/\/(127\.0\.0\.1|localhost)(:9443)(\/|$)/, "https://$1$2$3");
    // trim trailing slashes
    return s.replace(/\/+$/, "");
  }

  // Getter function (do NOT shadow with element reference)
  function backend() {
    var def = "https://localhost:9443";
    var fromUI = val(els.backend);
    var fromLS = readLS(LS_KEY);
    var fromOld = readLS(LS_KEY_OLD);
    return normBase(fromUI || fromLS || fromOld || def);
  }

  function _manifestSrc() { try { return window.location.href; } catch (_) { return ""; } }
  function normalizeText(s) { return (s ? String(s).replace(/\s+/g, " ").trim() : ""); }

  function sha256Hex(str) {
    if (window.crypto && window.crypto.subtle && window.TextEncoder) {
      var enc = new TextEncoder().encode(str);
      return crypto.subtle.digest("SHA-256", enc).then(function (buf) {
        var a = Array.from(new Uint8Array(buf));
        return a.map(function (b) { return ("00" + b.toString(16)).slice(-2); }).join("");
      });
    }
    var h = 2166136261 >>> 0;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24); }
    return Promise.resolve(("00000000" + (h >>> 0).toString(16)).slice(-8));
  }

  function recordDoctor(entry) {
    try {
      REQ_LOG.push(entry);
      if (REQ_LOG.length > 20) REQ_LOG.splice(0, REQ_LOG.length - 20);
      if (els.doctorReqList) {
        var li = document.createElement("li");
        li.textContent = [
          entry.method || "GET",
          entry.path || "",
          "→", entry.status,
          entry.ok ? "OK" : "ERR",
          "cid:", entry.cid || "—",
          "ms:", entry.latencyMs != null ? entry.latencyMs : "—",
          "bytes:", entry.bytes || 0
        ].join(" ");
        els.doctorReqList.insertBefore(li, els.doctorReqList.firstChild);
        txt(els.doctorCid, entry.cid || "—");
        txt(els.doctorLatency, (entry.latencyMs != null ? entry.latencyMs + " ms" : "—"));
        txt(els.doctorPayload, entry.bytes != null ? String(entry.bytes) : "—");
      }
    } catch (_) {}
  }

  function readRespHeaders(x) {
    var hdr = function (n) { try { return x.getResponseHeader(n) || ""; } catch (_) { return ""; } };
    return {
      cid: hdr("x-cid"),
      xcache: hdr("x-cache"),
      schema: hdr("x-schema-version"),
      latencyHeader: hdr("x-latency-ms")
    };
  }

  function applyHeadersToBadgesAndStore(headers, latencyMs) {
    CAI_STORE.status.cid = headers && headers.cid ? headers.cid : null;
    CAI_STORE.status.xcache = headers && headers.xcache ? headers.xcache : null;
    CAI_STORE.status.schemaVersion = headers && headers.schema ? headers.schema : null;
    CAI_STORE.status.latencyMs = (typeof latencyMs === "number" ? latencyMs : CAI_STORE.status.latencyMs);

    txt(els.cidBadge, CAI_STORE.status.cid || "—");
    txt(els.xcacheBadge, CAI_STORE.status.xcache || "—");
    txt(els.schemaBadge, CAI_STORE.status.schemaVersion || "—");
    if (CAI_STORE.status.latencyMs != null) txt(els.latencyBadge, CAI_STORE.status.latencyMs + " ms");
  }

  function renderApiError(prefix, r) {
    var msg = r.problem && (r.problem.title || r.problem.code) ? (r.problem.title + (r.problem.detail ? ": " + r.problem.detail : "")) : ("HTTP " + r.http);
    status("✖ " + prefix + " error: " + msg);
  }

  async function doHealth() {
    CAI.Store.setBase(backend());
    var r = await CAI.API.health();
    CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
    renderMeta();
    toast(r.ok ? "Conn: 200" : "Conn error: " + r.http);
    return r;
  }

  async function doSummary(text) {
    CAI.Store.setBase(backend());
    var r = await CAI.API.summary(text);
    CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
    renderMeta();
    if (r.ok) CAI.Store.get().last.summary = r.data;
    else renderApiError("Summary", r);
    return r;
  }

  async function doGptDraft(text, mode) {
    CAI.Store.setBase(backend());
    var r = await CAI.API.gptDraft(text, mode || getModeOrDefault());
    CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
    renderMeta();
    if (r.ok) CAI.Store.get().last.draft = r.data; else renderApiError("Draft", r);
    return r;
  }

  async function doSuggest(text, mode) {
    CAI.Store.setBase(backend());
    var r = await CAI.API.suggest(text, mode || getModeOrDefault());
    CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
    renderMeta();
    if (r.ok) CAI.Store.get().last.suggest = r.data; else renderApiError("Suggest", r);
    return r;
  }

  async function apiQARecheck(text, rules) {
    CAI.Store.setBase(backend());
    var r = await CAI.API.qaRecheck(text, rules || []);
    CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
    renderMeta();
    if (!r.ok) renderApiError("QA", r);
    return r;
  }

  function clearStorageAndReload(){
    try { localStorage.clear(); } catch (e) {}
    if (window.caches) { caches.keys().then(function(keys){ keys.forEach(function(k){ caches.delete(k); }); }); }
    location.reload();
  }

  // ===== Office helpers =====

  function ensureOfficeBadge() {
    try {
      if (!window.Office || !Office.onReady) { txt(els.officeBadge, "Office: —"); return; }
      Office.onReady(function (info) {
        txt(els.officeBadge, "Office: " + (info && info.host ? info.host : "Ready"));
      });
    } catch (_) { txt(els.officeBadge, "Office: error"); }
  }

  async function getSelectionText() {
    if (!window.Word || !Word.run) return "";
    return Word.run(async function (ctx) {
      var sel = ctx.document.getSelection();
      sel.load("text");
      await ctx.sync();
      return (sel.text || "").trim();
    });
  }

  async function getWholeDocText() {
    if (!window.Word || !Word.run) return "";
    return Word.run(async function (ctx) {
      var body = ctx.document.body;
      body.load("text");
      await ctx.sync();
      return (body.text || "").trim();
    });
  }

  function readSelection() { return getSelectionText(); }
  function readWholeDoc() { return getWholeDocText(); }

  async function resolveTextFromUI(){
    var ta = document.getElementById("input");
    var text = ta && ta.value ? ta.value.trim() : "";
    if (!text) text = await getSelectionText();
    if (!text) text = await getWholeDocText();
    return text.trim();
  }

  async function copySelection() {
    if (!window.Word || !Word.run) { status("⚠️ Word API not available"); return; }
    await Word.run(async function (ctx) {
      var range = ctx.document.getSelection();
      range.load("text");
      await ctx.sync();
      var t = (range.text || "").trim();
      setVal(els.clause, t);
      state.clauseText = t;
      console.info("[STATUS] Selection copied.");
      status("Selection copied.");
    });
  }

  async function copyWholeDoc() {
    if (!window.Word || !Word.run) { status("⚠️ Word API not available"); return; }
    await Word.run(async function (ctx) {
      var body = ctx.document.body;
      body.load("text");
      await ctx.sync();
      var t = (body.text || "").trim();
      setVal(els.clause, t);
      state.docText = t;
      state.clauseText = t;
      console.info("[STATUS] Whole document copied.");
      status("Whole document copied.");
    });
  }

  async function insertPlain(text) {
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function (ctx) {
      var sel = ctx.document.getSelection();
      sel.insertText(String(text || ""), "Replace");
      return ctx.sync();
    });
  }

  async function applyTracked(text, commentText) {
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function (ctx) {
      try { if (ctx.document && ctx.document.changeTrackingMode) ctx.document.changeTrackingMode = Word.ChangeTrackingMode.trackAll; } catch (_) {}
      var sel = ctx.document.getSelection(); sel.load("text");
      return ctx.sync().then(function () {
        sel.insertText(String(text || ""), "Replace");
        try { sel.insertComment(commentText || "Contract AI — applied draft"); } catch (_) {}
        return ctx.sync();
      });
    });
  }

  async function insertTextIntoWordWithTrackedChanges(text, comment){
    return applyTracked(text, comment);
  }

  async function acceptAll() {
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function (ctx) { try { ctx.document.acceptAllChanges(); } catch (_) {} return ctx.sync(); });
  }

  async function rejectAll() {
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function (ctx) { try { ctx.document.rejectAllChanges(); } catch (_) {} return ctx.sync(); });
  }

  function _riskOrd(v) {
    v = String(v || "").toLowerCase();
    if (v === "critical") return 3;
    if (v === "high") return 2;
    if (v === "medium") return 1;
    return 0;
  }

  function emojiForSeverity(s) {
    var m = String(s || "").toLowerCase();
    if (m === "critical") return "🚑";
    if (m === "high") return "🔥";
    if (m === "medium") return "⚠️";
    if (m === "low") return "ℹ️";
    if (m === "info") return "💡";
    return "♻";
  }

  function setBadges(a) {
    var risk = a && (a.risk || a.risk_level);
    txt(els.badgeScore, (a && a.score != null ? String(a.score) : "—"));
    txt(els.badgeRisk, (risk ? String(risk) : "—"));
    txt(els.badgeStatus, (a && a.status ? String(a.status) : "—"));
    var sev = a && (a.severity || (risk === "critical" ? "high" : risk));
    txt(els.badgeSev, (sev ? String(sev) : "—"));
  }

  function clearResults() {
    txt(els.resClauseType, "—");
    txt(els.resFindingsCount, "—");
    if (els.findingsList) els.findingsList.innerHTML = "";
    if (els.recoList) els.recoList.innerHTML = "";
    if (els.rawJson) { els.rawJson.textContent = ""; els.rawJson.style.display = "none"; }
    if (els.docSnap) { els.docSnap.innerHTML = ""; els.docSnap.classList.add("hidden"); }
  }

  function renderAnalysis(analysis) {
    if (!analysis) { clearResults(); return; }
    setBadges(analysis);
    txt(els.resClauseType, analysis.clause_type || "—");

    var findings = [];
    if (Array.isArray(analysis.findings)) findings = analysis.findings;
    var recs = [];
    if (Array.isArray(analysis.recommendations)) recs = analysis.recommendations;

    findings.sort(function (a, b) {
      var ra = _riskOrd(a && (a.risk || a.risk_level));
      var rb = _riskOrd(b && (b.risk || b.risk_level));
      if (rb !== ra) return rb - ra;
      var sa = String(a && a.severity || "");
      var sb = String(b && b.severity || "");
      if (sa !== sb) return (sa > sb ? -1 : 1);
      var pa = (a && a.span && typeof a.span.start === "number") ? a.span.start : 1e9;
      var pb = (b && b.span && typeof b.span.start === "number") ? b.span.start : 1e9;
      return pa - pb;
    });

    txt(els.resFindingsCount, String(findings.length));

    if (els.findingsList) {
      els.findingsList.innerHTML = "";
      if (!findings.length) {
        var li = document.createElement("li"); li.textContent = "No findings returned.";
        els.findingsList.appendChild(li);
      } else {
        findings.forEach(function (f) {
          var li = document.createElement("li");
          var sev = emojiForSeverity(f && (f.severity || f.risk || f.risk_level));
          var code = f && f.code ? ("[" + f.code + "] ") : "";
          var msg = f && f.message ? f.message : "—";
          var ev = f && f.evidence ? (" — evidence: “" + f.evidence + "”") : "";
          var lb = (f && f.legal_basis && f.legal_basis.length) ? (" — legal: " + f.legal_basis.join("; ")) : "";
          li.textContent = sev + " " + code + msg + ev + lb;
          els.findingsList.appendChild(li);
        });
      }
    }

    if (els.recoList) {
      els.recoList.innerHTML = "";
      if (!recs.length) {
        var li2 = document.createElement("li"); li2.textContent = "No recommendations.";
        els.recoList.appendChild(li2);
      } else {
        recs.forEach(function (r) {
          var li = document.createElement("li"); li.textContent = String(r);
          els.recoList.appendChild(li);
        });
      }
    }

    if (els.rawJson) {
      try { els.rawJson.textContent = JSON.stringify(analysis, null, 2); } catch (_) { els.rawJson.textContent = "Unable to stringify analysis."; }
    }
  }

  function renderAnalyze(resp){
    if(resp && resp.analysis) renderAnalysis(resp.analysis);
  }

  function pickDocType(summary) {
      summary = summary || {};
      var list = [];
      if (Array.isArray(summary.doc_types)) list = summary.doc_types;
      else if (summary.document && Array.isArray(summary.document.doc_types)) list = summary.document.doc_types;
      // legacy: summary.doc_type = { top:{type,score}, confidence, candidates[] }
      if (!list.length && summary.doc_type && (summary.doc_type.top || summary.doc_type.candidates)) {
        var top = summary.doc_type.top || {};
        var conf = (typeof summary.doc_type.confidence === 'number')
          ? summary.doc_type.confidence
          : (typeof top.score === 'number' ? top.score : null);
        return { name: top.type || top.name || null, confidence: conf };
      }
      var best = null;
      if (list && list.length) {
        best = list.reduce(function (acc, cur) {
          var c = typeof cur.confidence === 'number' ? cur.confidence : (typeof cur.score === 'number' ? cur.score : 0);
          var n = cur.name || cur.type || cur.slug || cur.id || null;
          if (!acc || c > acc.confidence) return { name: n, confidence: c };
          return acc;
        }, null);
      } else {
        var n2 = summary.type || (summary.document && summary.document.type) || null;
        var c2 = summary.type_confidence;
        if (c2 == null && summary.document && summary.document.type_confidence != null) c2 = summary.document.type_confidence;
        if (typeof c2 === 'string') { var f = parseFloat(c2); c2 = isNaN(f) ? null : f; }
        best = { name: n2, confidence: c2 };
      }
      return best || { name: null, confidence: null };
    }

  function renderDocSnapshot(info) {
      // якщо дали обгортку — дістань власне summary
      if (info && info.summary && !info.type && !info.doc_types && !info.doc_type) {
        info = info.summary;
      }
      if (!els.docSnap) return;
      if (!info) { els.docSnap.innerHTML = ""; els.docSnap.classList.add("hidden"); return; }
      var dt = pickDocType(info);
      var html = '<div class="flex" style="justify-content:space-between;align-items:center">';
      html += '<strong>Document Snapshot</strong>';
      if (CAI_STORE.status.schemaVersion) html += '<span class="muted">v' + esc(CAI_STORE.status.schemaVersion) + '</span>';
      html += '</div>';
      html += '<div class="grid">';
      html += '<div class="kv"><strong>Type:</strong><span data-snap-type>' + esc(dt && dt.name ? dt.name : '—') + '</span></div>';
      var conf = (dt && typeof dt.confidence === "number") ? dt.confidence : '—';
      html += '<div class="kv"><strong>Confidence:</strong><span data-snap-type-confidence>' + conf + '</span></div>';
      html += '</div>';
      if (Array.isArray(info.parties) && info.parties.length) {
        html += '<div style="margin-top:6px"><strong>Parties</strong><table><tr><th>Role</th><th>Name</th></tr>';
        info.parties.forEach(function(p){
          html += '<tr><td>' + esc(p.role || '—') + '</td><td>' + esc(p.name || '—') + '</td></tr>';
        });
      html += '</table></div>';
    }
    if (info.dates) {
      html += '<div class="grid" style="margin-top:6px">';
      html += '<div class="kv"><strong>Dated:</strong><span>' + esc(info.dates.dated || '—') + '</span></div>';
      html += '<div class="kv"><strong>Effective:</strong><span>' + esc(info.dates.effective || '—') + '</span></div>';
      html += '<div class="kv"><strong>Commencement:</strong><span>' + esc(info.dates.commencement || '—') + '</span></div>';
      html += '<div class="kv"><strong>Signatures:</strong><span>' + (info.signatures && info.signatures.length ? info.signatures.length : 0) + '</span></div>';
      html += '</div>';
    }
    if (info.term) {
      html += '<div class="grid" style="margin-top:6px">';
      html += '<div class="kv"><strong>Mode:</strong><span>' + esc(info.term.mode || '—') + '</span></div>';
      html += '<div class="kv"><strong>Start:</strong><span>' + esc(info.term.start || '—') + '</span></div>';
      html += '<div class="kv"><strong>End:</strong><span>' + esc(info.term.end || '—') + '</span></div>';
      html += '<div class="kv"><strong>Notice:</strong><span>' + esc(info.term.renew_notice || '—') + '</span></div>';
      html += '</div>';
    }
    if (info.governing_law) {
      html += '<div class="kv" style="margin-top:6px"><strong>Governing law:</strong><span>' + esc(info.governing_law) + '</span></div>';
    }
    if (info.jurisdiction) {
      html += '<div class="kv"><strong>Jurisdiction:</strong><span>' + esc(info.jurisdiction) + '</span></div>';
    }
    var liab = info.liability || {};
    var cap = liab.has_cap ? (liab.cap_value != null ? String(liab.cap_value) + (liab.cap_currency || '') : 'yes') : 'No cap';
    html += '<div class="kv" style="margin-top:6px"><strong>Liability cap:</strong><span>' + esc(cap) + '</span></div>';
    var excl = info.exclusivity == null ? '—' : (info.exclusivity ? 'exclusive' : 'non-exclusive');
    html += '<div class="kv"><strong>Exclusivity:</strong><span>' + esc(excl) + '</span></div>';
    var carveCount = (info.carveouts && Array.isArray(info.carveouts.carveouts)) ? info.carveouts.carveouts.length : 0;
    html += '<div class="kv"><strong>Carve-outs:</strong><span>' + carveCount + '</span></div>';
    var cw = info.conditions_vs_warranties || {};
    html += '<div class="kv"><strong>Conditions vs Warranties:</strong><span>' +
      'C:' + (cw.has_conditions ? 'yes' : 'no') + ' / W:' + (cw.has_warranties ? 'yes' : 'no') + '</span></div>';
    if (info.hints && info.hints.length) {
      html += '<div class="toggle" id="docSnapEv">Show evidence</div><ul id="docSnapHints" style="display:none;margin:6px 0 0 0">';
      info.hints.forEach(function(h){ html += '<li>' + esc(h) + '</li>'; });
      html += '</ul>';
    }
    html += '<div class="btn-row" style="margin-top:6px"><button id="docSnapCopy">Copy JSON</button><button id="docSnapInsert">Insert result into Word</button></div>';
    html += '<div class="toggle" id="docSnapToggle">Show raw JSON</div><pre id="docSnapRaw" style="display:none"></pre>';
    els.docSnap.innerHTML = html;
    els.docSnap.classList.remove('hidden');
    var tog = document.getElementById('docSnapToggle');
    var raw = document.getElementById('docSnapRaw');
    if (tog && raw) {
      try { raw.textContent = JSON.stringify(info, null, 2); } catch (_) { raw.textContent = ''; }
      tog.addEventListener('click', function(){ var s = raw.style.display; raw.style.display = (s === 'none' || !s) ? 'block' : 'none'; });
    }
    var ev = document.getElementById('docSnapEv');
    var evList = document.getElementById('docSnapHints');
    if (ev && evList) {
      ev.addEventListener('click', function(){ var s = evList.style.display; evList.style.display = (s === 'none' || !s) ? 'block' : 'none'; });
    }
    var cpy = document.getElementById('docSnapCopy');
    if (cpy) {
      cpy.addEventListener('click', function(){ try { navigator.clipboard.writeText(JSON.stringify(info, null, 2)); } catch (_) {} });
    }
    var ins = document.getElementById('docSnapInsert');
    if (ins && window.Office && Office.context && Office.context.document) {
      ins.addEventListener('click', function(){ try { Office.context.document.setSelectedDataAsync(JSON.stringify(info)); } catch (_) {} });
    }
  }

  function fillClauseSelect(envelope) {
    var clauses = (envelope && envelope.clauses) || [];
    els.sugSelect.innerHTML = "";
    clauses.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c && c.id ? c.id : "";
      var ttl = (c && (c.title || c.type)) || "clause";
      opt.textContent = (c && c.id ? c.id : "—") + " · " + ttl;
      els.sugSelect.appendChild(opt);
    });
  }

  function enableDraftApply(on) {
    en(els.btnPreviewDiff, on);
    en(els.btnApplyTracked, on);
    en(els.btnAcceptAll, on);
    en(els.btnRejectAll, on);
  }

  function setApplyEnabled(on) { enableDraftApply(on); }

  function normalizeSuggestion(s) {
    var d = {};
    try {
      if (s && typeof s === "object" && typeof s.model_dump === "function") {
        d = s.model_dump();
      } else if (s && typeof s === "object" && !Array.isArray(s)) {
        d = Object.assign({}, s);
      } else if (typeof s === "string") {
        d = { message: s, proposed_text: s };
      } else if (Array.isArray(s)) {
        if (s.length === 1) d = { message: String(s[0]) };
        else if (s.length === 2 && typeof s[0] !== "object" && typeof s[1] !== "object") d = { message: String(s[0]), proposed_text: String(s[1]) };
        else {
          try { d = Object.fromEntries(s); } catch (_) { d = { message: s.map(function (x) { return String(x); }).join(" ") }; }
        }
      } else {
        d = { message: String(s) };
      }
    } catch (_) { d = { message: "" }; }

    if (!d.message || typeof d.message !== "string") {
      d.message = d.text || d.proposed_text || d.proposed || "";
      if (typeof d.message !== "string") d.message = String(d.message || "");
    }

    var start = 0, length = 0, r = d.range, sp = d.span;
    try {
      if (r && typeof r === "object" && !Array.isArray(r)) {
        start = parseInt(r.start != null ? r.start : 0, 10) || 0;
        if (r.length != null) length = parseInt(r.length, 10) || 0;
        else if (r.end != null) length = Math.max(0, (parseInt(r.end, 10) || 0) - start);
      } else if (sp && typeof sp === "object" && !Array.isArray(sp)) {
        start = parseInt(sp.start != null ? sp.start : 0, 10) || 0;
        if (sp.length != null) length = parseInt(sp.length, 10) || 0;
        else {
          var endS = parseInt(sp.end != null ? sp.end : start, 10) || start;
          length = Math.max(0, endS - start);
        }
      } else if (Array.isArray(sp) && sp.length === 2) {
        var s0 = parseInt(sp[0], 10) || 0;
        var s1 = parseInt(sp[1], 10) || 0;
        start = Math.max(0, s0);
        length = Math.max(0, s1 - s0);
      }
    } catch (_) { start = 0; length = 0; }
    if (start < 0) start = 0;
    if (length < 0) length = 0;
    d.range = { start: start, length: length };
    return d;
  }

  function renderSuggestions(list) {
    els.sugList.innerHTML = "";
    var items = Array.isArray(list) ? list.slice() : [];
    items = items.map(normalizeSuggestion);

    if (!items.length) {
      var div = document.createElement("div"); div.className = "muted"; div.textContent = "No suggestions.";
      els.sugList.appendChild(div); return;
    }
    items.forEach(function (sug, i) {
      var card = document.createElement("div"); card.className = "sug-card";
      var head = document.createElement("div"); head.className = "sug-head";
      var title = document.createElement("div"); title.className = "sug-title";
      title.textContent = sug.title || (sug.clause_type ? (sug.clause_type + " suggestion") : ("Suggestion " + (i + 1)));
      var meta = document.createElement("div"); meta.className = "sug-meta";
      var rng = sug.range ? ("@" + sug.range.start + "×" + sug.range.length) : "";
      meta.textContent = (sug.risk ? ("risk:" + sug.risk + " ") : "") + rng;
      head.appendChild(title); head.appendChild(meta);

      var msg = document.createElement("div");
      msg.className = "sug-msg";
      msg.textContent = sug.message || "";

      var pre = document.createElement("pre");
      pre.textContent = sug.draft || sug.proposed_text || sug.text || "";

      var row = document.createElement("div");
      var btn = document.createElement("button"); btn.className = "btn"; btn.textContent = "Apply → Draft";
      btn.addEventListener("click", function () {
        setVal(els.draft, pre.textContent);
        window.LAST_DRAFT = pre.textContent;
        enableDraftApply(!!pre.textContent);
        status("Suggestion copied to draft. Review, then Apply.");
      });
      var btnPrev = document.createElement("button"); btnPrev.className = "btn btn-secondary"; btnPrev.textContent = "Preview";
      btnPrev.addEventListener("click", function () {
        setVal(els.draft, pre.textContent);
        window.LAST_DRAFT = pre.textContent;
        enableDraftApply(!!pre.textContent);
        status("Preview loaded into draft box.");
      });
      row.appendChild(btn);
      row.appendChild(btnPrev);

      card.appendChild(head);
      card.appendChild(msg);
      card.appendChild(pre);
      card.appendChild(row);
      els.sugList.appendChild(card);
    });
  }

  window.CAI_renderSuggestions = function (list) {
    try {
      var items = Array.isArray(list) ? list : [];
      renderSuggestions(items);
    } catch (e) {
      status("Render suggestions failed: " + (e && e.message ? e.message : e));
    }
  };

  function diffHTML(a, b) {
    var aw = a.split(/(\s+)/);
    var bw = b.split(/(\s+)/);
    var m = aw.length, n = bw.length;
    var dp = Array(m + 1); for (var i = 0; i <= m; i++) { dp[i] = Array(n + 1).fill(0); }
    for (var i1 = 1; i1 <= m; i1++) {
      for (var j1 = 1; j1 <= n; j1++) {
        if (aw[i1 - 1] === bw[j1 - 1]) dp[i1][j1] = dp[i1 - 1][j1 - 1] + 1;
        else dp[i1][j1] = dp[i1 - 1][j1] >= dp[i1][j1 - 1] ? dp[i1 - 1][j1] : dp[i1][j1 - 1];
      }
    }
    var res = [];
    var i2 = m, j2 = n;
    while (i2 > 0 && j2 > 0) {
      if (aw[i2 - 1] === bw[j2 - 1]) { res.push(esc(aw[i2 - 1])); i2--; j2--; }
      else if (dp[i2 - 1][j2] >= dp[i2][j2 - 1]) { res.push('<del>' + esc(aw[i2 - 1]) + '</del>'); i2--; }
      else { res.push('<ins>' + esc(bw[j2 - 1]) + '</ins>'); j2--; }
    }
    while (i2 > 0) { res.push('<del>' + esc(aw[i2 - 1]) + '</del>'); i2--; }
    while (j2 > 0) { res.push('<ins>' + esc(bw[j2 - 1]) + '</ins>'); j2--; }
    return res.reverse().join('');
  }

  // ===== Flows =====

  async function doHealthFlow() {
    txt(els.connBadge, "Conn: …");
    return await doHealth();
  }

  async function analyzeDoc() {
    const text = getOriginalClauseText && await getOriginalClauseText();
    const mode = CAI.Store.get().risk || "medium";
    if (!text || !text.trim()) { toast("⚠️ Paste or copy text first."); return; }
    const r = await CAI.API.analyze(text, mode);
    CAI.Store.setMeta({
      cid: r.meta.headers.cid, cache: r.meta.headers.cache, latencyMs: r.meta.latencyMs,
      schema: r.meta.schema, provider: r.meta.headers.provider, model: r.meta.headers.model,
      llm_mode: r.meta.headers.llm_mode, usage: r.meta.headers.usage
    });
    renderMeta();
    if (r.ok) {
      CAI.Store.get().last.analyze = r.data.analysis;
      if (els.commentOnAnalyze && els.commentOnAnalyze.checked) {
        await CAI.commentAllFindings(r.data?.analysis?.findings, r.meta.headers);
      }
      renderFindings(r.data.analysis);
    } else {
      renderApiError("Analyze", r);
    }
  }

  function renderFindings(a){
    setText("resClauseType", a && a.clause_type || "—");
    renderFindingsList(a && a.findings || []);
    renderRecommendationsList(a && a.recommendations || []);
  }

  function renderFindingsList(items){
    const c = document.getElementById("findingsList");
    if (!c) return;
    c.innerHTML = "";
    if (!items.length) { c.innerHTML = "<div class='muted'>—</div>"; return; }
    for (const f of items) {
      const li = document.createElement("div");
      li.className = "kv";
      li.innerHTML = `<strong>${f.clause_type || f.rule_id || "rule"}</strong><span>${f.severity || ""}</span><div>${escapeHtml(f.advice || f.snippet || "")}</div>`;
      c.appendChild(li);
    }
  }
  function renderRecommendationsList(items){
    const c = document.getElementById("recoList");
    if (!c) return;
    c.innerHTML = "";
    if (!items.length) { c.innerHTML = "<div class='muted'>—</div>"; return; }
    for (const r of items) {
      const li = document.createElement("div");
      li.className = "kv";
      li.innerHTML = `<div>${escapeHtml(r.text || r.advice || "")}</div>`;
      c.appendChild(li);
    }
  }

  async function onSuggest() {
    var mode = getModeOrDefault();
    var text = await getPanelTextOrFetch();
    if (!text) { toast("Document is empty"); return; }
    try {
      var r = await doSuggest(text, mode);
      if (r.ok) {
        var payload = r.data || {};
        var prop = payload.proposed_text || payload.suggested_text || payload.text || "";
        setVal(els.draft, prop);
        state.proposedText = prop;
        setApplyEnabled(!!prop);
        window._orig = text;
        window._prop = prop;
        renderDiff(window._orig, window._prop);
        status(prop ? "Suggest OK" : "Nothing to suggest for this clause");
      }
    } catch (e) { status("✖ Suggest error: " + (e && e.message ? e.message : e)); }
  }

  async function doGptDraft() {
    const text = getOriginalClauseText && await getOriginalClauseText();
    if (!text || !text.trim()) { toast("⚠️ Paste or copy text first."); return; }

    const r = await CAI.API.gptDraft(text, getDraftMode());
    CAI.Store.setMeta({
      cid: r.meta.headers.cid, cache: r.meta.headers.cache, latencyMs: r.meta.latencyMs,
      schema: r.meta.schema, provider: r.meta.headers.provider, model: r.meta.headers.model,
      llm_mode: r.meta.headers.llm_mode, usage: r.meta.headers.usage
    });
    renderMeta();

    const D = mapDraft(r);
    CAI.Store.get().last.draft = r.data;

    if (!D.ok) { renderApiError("Draft", r); return; }

    const t = document.getElementById("draftText");
    if (t) t.value = D.proposed || D.after || "";

    const btnPrev = document.getElementById("btnPreviewDiff");
    if (btnPrev) {
      btnPrev.onclick = () => {
        const diff = D.diff || "";
        if (diff) showModal("Unified diff", diff);
        else showModal("Unified diff", "No diff provided by backend.");
      };
    }

    toast("Draft OK");
  }

  document.getElementById("btnApplyTracked").addEventListener("click", async function(){
    const draft = getDraftText();
    if (!draft || !draft.trim()) { toast("Nothing to apply."); return; }
    await Word.run(async (ctx) => {
      const useWhole = lastCopiedWasWhole();
      const sel = useWhole ? ctx.document.body.getRange() : ctx.document.getSelection();
      sel.track();
      await ctx.sync();
      ctx.trackedRevisions.trackAll();
      sel.insertText(draft, Word.InsertLocation.replace);
      await ctx.sync();
    });
    toast("Applied");
  });

  async function doAnalyze() {
    var text = await getPanelTextOrFetch();
    if (!text) { toast("Document is empty"); return; }
    status("Analyzing…");
    clearResults();
    try {
      var s = await doSummary(text);
      if (s.ok) {
        var senv = s.data.summary || s.data;
        CAI_STORE.analysis.snapshot = senv;
        renderDocSnapshot(senv);
      } else {
        renderDocSnapshot(null);
      }
      CAI.Store.setBase(backend());
      var r = await CAI.API.analyze(text, getModeOrDefault());
      CAI.Store.setMeta({ cid:r.meta.headers.cid, cache:r.meta.headers.cache, latencyMs:r.meta.latencyMs, schema:r.meta.schema, provider:r.meta.headers.provider, model:r.meta.headers.model, llm_mode:r.meta.headers.llm_mode, usage:r.meta.headers.usage });
      renderMeta();
      if (r.ok) {
        var env = r.data;
        CAI_STORE.analysis.analysis = env.analysis || env;
        CAI_STORE.analysis.results = env.results || null;
        CAI_STORE.analysis.clauses = Array.isArray(env.clauses) ? env.clauses : [];
        CAI_STORE.analysis.document = env.document || null;
        CAI.Store.get().last.analyze = env.analysis || null;
        if (els.commentOnAnalyze && els.commentOnAnalyze.checked) {
          await CAI.commentAllFindings((env.analysis || env)?.findings, r.meta.headers);
        }
        fillClauseSelect(env);
        renderAnalysis(CAI_STORE.analysis.analysis);
        status("Analyze OK");
      } else {
        renderApiError("Analyze", r);
      }
    } catch (e) { status("✖ Analyze error: " + (e && e.message ? e.message : e)); }
  }

  async function insertAnnotations(ann){
    await Word.run(async (ctx) => {
      const body = ctx.document.body;
      const whole = body.getRange();
      whole.load("text");
      await ctx.sync();

      const text = whole.text;
      for (const x of ann) {
        const found = whole.search(x.anchor || "", { matchCase:false, matchWholeWord:false, ignorePunct:true });
        found.load("items");
        await ctx.sync();
        if (found.items.length > 0) {
          const r = found.items[0];
          ctx.trackedRevisions.trackAll();
          r.insertComment(`[${x.severity}] ${x.title || "Issue"} — ${x.message}`);
        }
      }
      await ctx.sync();
    });
  }

  async function doQARecheck() {
    var full = await getPanelTextOrFetch();
    if (!full) { toast("Document is empty"); return; }
    status("QA recheck…");
    try {
      var r = await apiQARecheck(full, []);
      if (r.ok) {
        var env = r.data || {};
        var d = env.deltas || env || {};
        var scoreDelta = d.score_delta || 0;
        var riskDelta = d.risk_delta || 0;
        var badge = "Δ: s" + (scoreDelta >= 0 ? "+" : "") + (scoreDelta || 0) +
          " r" + (riskDelta >= 0 ? "+" : "") + (riskDelta || 0) +
          " " + (d.status_from || "") + "→" + (d.status_to || "");
        txt(els.qaDeltaBadge, badge);

        var res = env.residual_risks || [];
        els.qaResidualList.innerHTML = "";
        if (res.length) {
          els.qaResiduals.style.display = "block";
          res.forEach(function (it) {
            var li = document.createElement("li");
            li.textContent = (it.code ? ("[" + it.code + "] ") : "") + (it.message || "risk");
            els.qaResidualList.appendChild(li);
          });
        } else {
          els.qaResiduals.style.display = "none";
        }
        status("QA OK");
      }
    } catch (e) { status("✖ QA error: " + (e && e.message ? e.message : e)); }
  }

  // ===== Wiring =====

  function wire() {
    els.backend = $("backendUrl");
    els.btnSave = $("btnSave");
    els.btnTest = $("btnTest");
    els.buildInfo = $("buildInfo");
    els.connBadge = $("connBadge");
    els.officeBadge = $("officeBadge");
    els.cidBadge = $("cidBadge");
    els.xcacheBadge = $("xcacheBadge");
    els.latencyBadge = $("latencyBadge");
    els.schemaBadge = $("schemaBadge");
    els.providerBadge = $("providerBadge");
    els.providerMeta = $("providerMeta");
    els.modelBadge = $("modelBadge");
    els.modeBadge = $("modeBadge");
    els.mockModeBadge = $("mockModeBadge");
    els.doctorToggle = $("doctorToggle");
    els.doctorPanel = $("doctorPanel");
    els.docSnap = $("doc-snapshot");
    els.doctorReqList = $("doctorReqList");
    els.doctorCid = $("doctorCid");
    els.doctorLatency = $("doctorLatency");
    els.doctorPayload = $("doctorPayload");

    els.clause = $("originalClause");
    els.analyzeBtn = $("analyzeBtn");
    els.draftBtn = $("draftBtn");
    els.copyBtn = $("copyResultBtn");
    els.useDoc = $("btn-use-whole");
    els.useSel = $("btn-use-selection");
    els.btnInsert = $("btnInsertIntoWord");

    els.btnAnalyzeDoc = $("btnAnalyzeDoc");
    els.btnAnnotate = $("btnAnnotate");
    els.btnQARecheck = $("btnQARecheck");
    els.btnClearAnnots = $("btnClearAnnots");
    els.qaDeltaBadge = $("qaDeltaBadge");
    els.qaResiduals = $("qaResiduals");
    els.qaResidualList = $("qaResidualList");
    els.riskThreshold = $("riskThreshold");
    els.commentOnAnalyze = $("cai-comment-on-analyze");

    els.badgeScore = $("scoreBadge");
    els.badgeRisk = $("riskBadge");
    els.badgeStatus = $("statusBadge");
    els.badgeSev = $("severityBadge");

    els.resClauseType = $("resClauseType");
    els.resFindingsCount = $("resFindingsCount");
    els.findingsList = $("findingsList");
    els.recoList = $("recoList");
    els.toggleRaw = $("toggleRaw");
    els.rawJson = $("rawJson");

    els.sugSelect = $("cai-clause-select");
    els.sugMode = $("cai-mode");
    els.sugBtn = $("btnSuggest");
    els.sugList = $("cai-suggest-list");

    els.draft = $("draftText");
    els.btnPreviewDiff = $("btnPreviewDiff");
    els.btnApplyTracked = $("btnApplyTracked");
    els.btnAcceptAll = $("btnAcceptAll");
    els.btnRejectAll = $("btnRejectAll");
    els.diffContainer = $("diffContainer");
    els.diffOutput = $("diffOutput");
    els.diffView = $("diffView");

    els.console = $("console");

    if (els.buildInfo) {
      try {
        var src = _manifestSrc();
        els.buildInfo.textContent = "Build: " + BUILD + " • " + src;
      } catch (_) { els.buildInfo.textContent = "Build: " + BUILD; }
    }

    // Base URL field initialized on load by Store

    if (els.btnSave) els.btnSave.addEventListener("click", function () {
      var v = backend(); if (!v) { status("⚠️ Enter backend URL first"); return; }
      writeLS(LS_KEY, v); CAI.Store.setBase(v); status("Saved: " + v);
    });

    if (els.btnTest) els.btnTest.addEventListener("click", function () { doHealthFlow(); });

    if (els.analyzeBtn) els.analyzeBtn.addEventListener("click", function () { doAnalyze(); });
    if (els.btnAnalyzeDoc) els.btnAnalyzeDoc.addEventListener("click", analyzeDoc);

    if (els.useDoc) els.useDoc.addEventListener("click", async function(){
      const text = await getWholeDocText();
      setOriginalText(text);
      state.docText = text;
      __lastCopiedWhole = true;
      toast("Whole document copied.");
    });
    if (els.useSel) els.useSel.addEventListener("click", async function(){
      const text = await getSelectionText();
      setOriginalText(text);
      __lastCopiedWhole = false;
      toast("Selection copied.");
    });

    if (els.draftBtn) els.draftBtn.addEventListener("click", function () { doGptDraft(); });
    if (els.copyBtn) els.copyBtn.addEventListener("click", function () {
      try { navigator.clipboard && navigator.clipboard.writeText(val(els.draft) || ""); status("Draft copied to clipboard"); } catch (_) {}
    });

    if (els.sugBtn) els.sugBtn.addEventListener("click", onSuggest);

    if (els.toggleRaw) els.toggleRaw.addEventListener("click", function () {
      if (!els.rawJson) return;
      var s = window.getComputedStyle(els.rawJson).display;
      els.rawJson.style.display = (s === "none" ? "block" : "none");
    });

    if (els.draft) els.draft.addEventListener("input", function () {
      state.proposedText = val(els.draft);
      setApplyEnabled(!!val(els.draft));
    });

    if (els.btnInsert) els.btnInsert.addEventListener("click", async function () {
      try {
        var t = val(els.draft).trim();
        if (!t) { status("Draft empty"); return; }
        await insertPlain(t);
        status("Inserted into Word (plain)");
      } catch (e) { status("✖ Insert failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnAcceptAll) els.btnAcceptAll.addEventListener("click", function () {
      var btn = document.getElementById("btnApplyTracked");
      if (btn) btn.click();
    });

    if (els.btnRejectAll) els.btnRejectAll.addEventListener("click", function () {
      window._prop = null;
      if (els.diffView) els.diffView.innerHTML = "";
      toast("Rejected");
    });

    if (els.btnAnnotate) els.btnAnnotate.addEventListener("click", async function () {
      const a = CAI.Store.get().last.analyze;
      if (!a || !a.annotations || !a.annotations.length) { toast("No annotations from last analyze."); return; }
      await insertAnnotations(a.annotations);
      toast("Annotations added.");
    });
    if (els.btnClearAnnots) els.btnClearAnnots.addEventListener("click", async function () {
      if (!window.Word || !Word.run) { status("⚠️ Word API not available"); return; }
      try {
        await Word.run(function (ctx) {
          var comments = ctx.document.body.comments; comments.load("items");
          return ctx.sync().then(function () {
            if (comments && comments.items) {
              comments.items.forEach(function (c) { try { c.delete(); } catch (_) {} });
            }
            return ctx.sync();
          });
        });
        status("Annotations cleared.");
      } catch (e) { status("✖ Clear annotations failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnQARecheck) els.btnQARecheck.addEventListener("click", function () { doQARecheck(); });

    if (els.doctorToggle) els.doctorToggle.addEventListener("click", function () {
      var vis = els.doctorPanel && (els.doctorPanel.style.display !== "none");
      els.doctorPanel.style.display = vis ? "none" : "block";
      els.doctorToggle.textContent = vis ? "Doctor ▾" : "Doctor ▸";
    });
  }

    function boot() {
      ensureOfficeBadge();
      status("📦 Bundle ready (" + BUILD + "). Set backend and click Test.");
      try { window.__CAI_WIRED__ = "ready"; } catch (_) {}
    }

    document.addEventListener("DOMContentLoaded", function(){
      try { wire(); } catch (e) { status("wire() failed: " + e); }
      try { boot(); } catch (e) { status("boot() failed: " + e); }
    }, { once: true });

  window.addEventListener("error", function (e) {
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[JS ERROR] " + (e.message || e.error || e) + "\n")); n.scrollTop = n.scrollHeight; } } catch (_) {}
  });
  window.addEventListener("unhandledrejection", function (e) {
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[PROMISE REJECTION] " + (e.reason && (e.reason.message || e.reason)) + "\n")); n.scrollTop = n.scrollHeight; } } catch (_) {}
  });

  })();

(function(){
  function withWord(fn){ return Word.run(async ctx => { try{ await fn(ctx); }catch(e){ console.error(e); throw e; } }); }
  async function ensureTracking(ctx){ ctx.document.trackRevisions = true; }
  function shortSig(s){ if(!s) return ""; const t = String(s).trim(); return t.length>80?t.slice(0,80):t; }
  async function findRangeByExcerpt(ctx, excerpt){
    const body = ctx.document.body;
    const q = shortSig(excerpt);
    let results = body.search(q, { matchCase:false, matchWholeWord:false, ignorePunct:true, ignoreSpace:true });
    results.load("items");
    await ctx.sync();
    if(results.items.length) return results.items[0];
    const q2 = shortSig(q.slice(0, Math.max(20, Math.floor(q.length/2))));
    results = body.search(q2, { matchCase:false, matchWholeWord:false, ignorePunct:true, ignoreSpace:true });
    results.load("items");
    await ctx.sync();
    return results.items[0] || null;
  }
  async function applyTrackedEdit(edit){
    await withWord(async ctx => {
      await ensureTracking(ctx);
      const range = await findRangeByExcerpt(ctx, edit.excerpt || edit.before_text);
      if(!range) throw new Error("Target text not found for edit " + edit.id);
      range.insertText(edit.after_text, "Replace");
      const cc = range.insertContentControl();
      cc.tag = "cai:sugg:" + edit.id;
      cc.title = "ContractAI Suggestion " + edit.id;
      cc.appearance = "Tags";
      range.insertComment("AI [" + edit.severity + "] " + edit.rule_id + (edit.title?" – "+edit.title:"") + (edit.recommendation?"\nRec: "+edit.recommendation:"") );
      await ctx.sync();
    });
    CAI.store && CAI.store.updateSuggestion && CAI.store.updateSuggestion(edit.id, { status:"applied", tag:"cai:sugg:"+edit.id });
  }
  function onApplyClick(id){
    const list = (CAI.store && CAI.store.get && CAI.store.get("cai:suggestions", [])) || [];
    const edit = list.find(x=>x.id===id);
    if(!edit) return;
    applyTrackedEdit(edit).then(renderSuggestions).catch(e=>{ console.error(e); });
  }
  function onAccept(id){ CAI.store && CAI.store.updateSuggestion && CAI.store.updateSuggestion(id, {status:"accepted"}); renderSuggestions(); }
  function onReject(id){ CAI.store && CAI.store.updateSuggestion && CAI.store.updateSuggestion(id, {status:"rejected"}); renderSuggestions(); }
  function renderSuggestions(){
    const root = document.getElementById("suggestions");
    const tpl = document.getElementById("sugg-item");
    if(!root || !tpl) return;
    root.innerHTML = "";
    const list = (CAI.store && CAI.store.get && CAI.store.get("cai:suggestions", [])) || [];
    for(const s of list){
      const node = tpl.content.cloneNode(true);
      const el = node.querySelector(".sugg-item");
      el.dataset.id = s.id;
      el.querySelector(".rule").textContent = s.rule_id || s.title || "Suggestion";
      el.querySelector(".sev").textContent = s.severity || "";
      el.querySelector(".before").textContent = s.before_text ? ("– "+s.before_text) : "";
      el.querySelector(".after").textContent = s.after_text ? ("→ "+s.after_text) : "";
      const st = el.querySelector(".status");
      st.textContent = s.status || "pending";
      if(s.status === "applied") st.classList.add("badge-applied");
      if(s.status === "accepted") st.classList.add("badge-accepted");
      if(s.status === "rejected") st.classList.add("badge-rejected");
      el.querySelector(".btn-apply").onclick = () => onApplyClick(s.id);
      el.querySelector(".btn-accept").onclick = () => onAccept(s.id);
      el.querySelector(".btn-reject").onclick = () => onReject(s.id);
      root.appendChild(node);
    }
  }
  document.addEventListener("DOMContentLoaded", renderSuggestions);
})();

(function(){
  function attachSafeFill(){
    const fill = (txt) => {
      try{
        const area = document.querySelector("#clause");
        if(area){ area.value = txt; }
        window.state = window.state || {};
        window.state.original_text = txt;
        window.state.doc_text = txt;
        console.log("[patch] clause filled, length=", (txt||"").length);
      }catch(e){ console.error("[patch] fill error", e); }
    };
    try{
      const modeSel = document.querySelector("#cai-mode");
      if(modeSel && !modeSel.querySelector('option[value="medium"]')){
        const friendlyOpt = modeSel.querySelector('option[value="friendly"]');
        const opt = document.createElement('option');
        opt.value = 'medium';
        opt.textContent = 'medium';
        if(friendlyOpt && friendlyOpt.nextSibling){
          modeSel.insertBefore(opt, friendlyOpt.nextSibling);
        }else{
          modeSel.appendChild(opt);
        }
      }
    }catch(e){ console.error("[patch] mode option error", e); }
    const btnWhole = document.querySelector("#btnUseWholeDoc, [data-action='use-whole-doc']");
    const btnSel   = document.querySelector("#btnUseSelection, [data-action='use-selection']");
    if(btnWhole && !btnWhole.__patched){
      btnWhole.__patched = true;
      btnWhole.addEventListener("click", async ()=>{
        try{
          await Word.run(async ctx=>{
            const body = ctx.document.body; body.load("text"); await ctx.sync();
            fill(body.text || "");
          });
        }catch(e){ console.error("[patch] whole-doc error", e); }
      }, true);
    }
    if(btnSel && !btnSel.__patched){
      btnSel.__patched = true;
      btnSel.addEventListener("click", async ()=>{
        try{
          await Word.run(async ctx=>{
            const sel = ctx.document.getSelection(); sel.load("text"); await ctx.sync();
            fill(sel.text || "");
          });
        }catch(e){ console.error("[patch] selection error", e); }
      }, true);
    }
  }
  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", attachSafeFill);
  }else{
    attachSafeFill();
  }
})();

window.__BUILD_ID__ = "panel-dev-" + new Date().toISOString().slice(0,10);
