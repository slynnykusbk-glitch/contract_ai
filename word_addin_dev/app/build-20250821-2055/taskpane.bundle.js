# word_addin_dev/taskpane.bundle.js
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

  var REQ_LOG = [];

  function $(id) { return document.getElementById(id); }
  function val(e) { return e ? (e.value || "") : ""; }
  function setVal(e, v) { if (e) e.value = (v == null ? "" : String(v)); }
  function txt(e, v) { if (e) e.textContent = (v == null ? "" : String(v)); }
  function en(e, on) { if (e) e.disabled = !on; }
  function log(s) {
    try {
      var n = els.console; if (!n) return;
      n.appendChild(document.createTextNode(String(s) + "\n"));
      n.scrollTop = n.scrollHeight;
    } catch (_) {}
  }
  function status(s) { log("[STATUS] " + s); }

  // LS keys (canonical + legacy fallback)
  var LS_KEY = "panel:backendUrl";
  var LS_KEY_OLD = "contract_ai_backend";

  function readLS(k) { try { return localStorage.getItem(k) || ""; } catch (_) { return ""; } }
  function writeLS(k, v) { try { localStorage.setItem(k, v); return true; } catch (_) { return false; } }

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
    var def = "https://127.0.0.1:9443";
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

  // Unified network wrapper (per passport)
  async function callEndpoint(opts) {
    opts = opts || {};
    var method = (opts.method || "GET").toUpperCase();
    var path = String(opts.path || "/");
    var body = opts.body || null;
    var timeoutMs = opts.timeoutMs || (method === "GET" ? 8000 : 30000);

    var base = backend();
    if (!base) throw new Error("backend not set");

    // Anti-cache for GET: add ?t=now
    var url = base + path;
    if (method === "GET") {
      url += (url.indexOf("?") === -1 ? "?" : "&") + "t=" + Date.now();
    }

    return new Promise(function (resolve, reject) {
      var x = new XMLHttpRequest();
      var t0 = (performance && performance.now) ? performance.now() : Date.now();
      var payload = (method === "POST" || method === "PUT" || method === "PATCH") ? JSON.stringify(body || {}) : null;

      x.open(method, url, true);
      x.setRequestHeader("x-panel-build", BUILD);
      x.setRequestHeader("x-manifest-src", _manifestSrc());
      x.setRequestHeader("x-cid", window.__CLIENT_CID__ || "");
      x.setRequestHeader("x-schema-version", "1.0");
      if (payload != null) x.setRequestHeader("Content-Type", "application/json");
      // pass-through custom headers (e.g., x-idempotency-key)
      if (opts.headers && typeof opts.headers === "object") {
        for (var hk in opts.headers) {
          if (Object.prototype.hasOwnProperty.call(opts.headers, hk)) {
            try { x.setRequestHeader(hk, String(opts.headers[hk])); } catch (_) {}
          }
        }
      }

      x.timeout = timeoutMs;
      x.onreadystatechange = function () {
        if (x.readyState === 4) {
          var t1 = (performance && performance.now) ? performance.now() : Date.now();
          var headers = readRespHeaders(x);
          var text = x.responseText || "";
          var json = null; try { json = text ? JSON.parse(text) : null; } catch (_) { json = null; }
          var latency = Math.max(0, Math.round(t1 - t0));
          applyHeadersToBadgesAndStore(headers, latency);
          recordDoctor({
            method: method, path: path, status: x.status, ok: (x.status >= 200 && x.status < 300),
            cid: headers.cid || (window.__CLIENT_CID__ || ""),
            latencyMs: latency, bytes: (payload ? payload.length : 0)
          });
          resolve({
            ok: (x.status >= 200 && x.status < 300),
            status: x.status,
            json: json,
            headers: headers,
            latencyMs: latency,
            xcid: headers.cid,
            xcache: headers.xcache,
            xschema: headers.schema
          });
        }
      };
      x.onerror = function () { reject(new Error("network error")); };
      x.ontimeout = function () { reject(new Error("timeout")); };
      x.send(payload);
    });
  }

  // ===== API functions (contracts) =====

  async function doHealth() {
    var res;
    try {
      res = await callEndpoint({ method: "GET", path: "/health", timeoutMs: 8000 });
      txt(els.connBadge, "Conn: " + res.status);
      return res;
    } catch (e) {
      txt(els.connBadge, "Conn: 0");
      status("✖ Health failed: " + (e && e.message ? e.message : e));
      return { ok: false, status: 0, json: null, headers: {} };
    }
  }

  async function apiAnalyze(opts) {
    opts = opts || {};
    var text = opts.text || "";
    var policyPack = null;
    var norm = normalizeText(text);
    var pol = "{}";
    var idem = await sha256Hex(norm + "|" + pol);
    try {
      return await callEndpoint({
        method: "POST",
        path: "/api/analyze",
        body: { text: text, policy_pack: policyPack },
        timeoutMs: 30000,
        headers: { "x-idempotency-key": idem }
      });
    } catch (e) {
      status("✖ Analyze error: " + (e && e.message ? e.message : e));
      return { ok: false, status: 0, json: null, headers: {} };
    }
  }

  // Back-compat wrapper (old signature)
  async function apiAnalyze_legacy(text) { return apiAnalyze({ text: text }); }

  async function apiGptDraft(opts) {
    opts = opts || {};
    var body = {};
    if (opts.analysis) body.analysis = opts.analysis;
    if (opts.text) body.text = opts.text;
    body.mode = opts.mode || "friendly";
    try {
      return await callEndpoint({ method: "POST", path: "/api/gpt/draft", body: body, timeoutMs: 25000 });
    } catch (e) {
      status("✖ Draft error: " + (e && e.message ? e.message : e));
      return { ok: false, status: 0, json: null, headers: {} };
    }
  }

  // Back-compat wrapper (old name)
  async function apiDraft(input) { return apiGptDraft(input || {}); }

  async function apiSuggestEdits(opts) {
    opts = opts || {};
    var body = {
      text: opts.text || "",
      clause_id: opts.clause || "",
      mode: opts.mode || "friendly",
      top_k: Math.min(10, Math.max(1, opts.top_k || 3))
    };
    try {
      return await callEndpoint({ method: "POST", path: "/api/suggest_edits", body: body, timeoutMs: 25000 });
    } catch (e) {
      status("✖ Suggest error: " + (e && e.message ? e.message : e));
      return { ok: false, status: 0, json: null, headers: {} };
    }
  }

  // Back-compat wrapper (old signature)
  async function apiSuggestEdits_legacy(text, clauseId, mode, topK) {
    return apiSuggestEdits({ text: text, clause: clauseId, mode: mode, top_k: topK });
  }

  async function apiQARecheck(fullText, residual) {
    var thr = (val(els.riskThreshold) || CAI_STORE.settings.riskThreshold || "high");
    var body = { text: fullText || "", threshold: thr, applied_changes: Array.isArray(residual) ? residual : [] };
    try {
      return await callEndpoint({ method: "POST", path: "/api/qa-recheck", body: body, timeoutMs: 20000 });
    } catch (e) {
      status("✖ QA error: " + (e && e.message ? e.message : e));
      return { ok: false, status: 0, json: null, headers: {} };
    }
  }

  async function apiLearningLog(events) {
    try {
      return await callEndpoint({
        method: "POST",
        path: "/api/learning/log",
        body: { events: Array.isArray(events) ? events.slice(0, 100) : [] },
        timeoutMs: 15000
      });
    } catch (e) { return { ok: false, status: 0, json: null, headers: {} }; }
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

  function readSelection() {
    if (!window.Word || !Word.run) return Promise.resolve("");
    return Word.run(function (ctx) {
      var s = ctx.document.getSelection(); s.load("text");
      return ctx.sync().then(function () { return s.text || ""; });
    });
  }

  function readWholeDoc() {
    if (!window.Word || !Word.run) return Promise.resolve(val(els.clause) || "");
    return Word.run(function (ctx) {
      var b = ctx.document.body; b.load("text");
      return ctx.sync().then(function () { return b.text || ""; });
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
    if (els.recsList) els.recsList.innerHTML = "";
    if (els.rawJson) { els.rawJson.textContent = ""; els.rawJson.style.display = "none"; }
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

    if (els.recsList) {
      els.recsList.innerHTML = "";
      if (!recs.length) {
        var li2 = document.createElement("li"); li2.textContent = "No recommendations.";
        els.recsList.appendChild(li2);
      } else {
        recs.forEach(function (r) {
          var li = document.createElement("li"); li.textContent = String(r);
          els.recsList.appendChild(li);
        });
      }
    }

    if (els.rawJson) {
      try { els.rawJson.textContent = JSON.stringify(analysis, null, 2); } catch (_) { els.rawJson.textContent = "Unable to stringify analysis."; }
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
    en(els.btnPreview, on);
    en(els.btnApply, on);
    en(els.btnAcceptAll, on);
    en(els.btnRejectAll, on);
  }

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

  // ===== Flows =====

  async function doHealthFlow() {
    txt(els.connBadge, "Conn: …");
    var r = await doHealth();
    // Badges are applied by callEndpoint; just echo status result here
    return r;
  }

  async function doAnalyze(useWhole) {
    var text = useWhole ? await readWholeDoc() : (val(els.clause) || "");
    if (!text || !text.trim()) { status("⚠️ No text to analyze."); return; }
    status("Analyzing…");
    clearResults();
    try {
      var r = await apiAnalyze({ text: text });
      if (!r.ok) { status("Analyze HTTP " + r.status); return; }
      var payload = r.json || {};
      var env = payload.data || payload;
      CAI_STORE.analysis.analysis = env.analysis || env;
      CAI_STORE.analysis.results = env.results || null;
      CAI_STORE.analysis.clauses = Array.isArray(env.clauses) ? env.clauses : [];
      CAI_STORE.analysis.document = env.document || null;

      txt(els.cidBadge, CAI_STORE.status.cid || "—");
      txt(els.xcacheBadge, CAI_STORE.status.xcache || "—");
      if (CAI_STORE.status.latencyMs != null) txt(els.latencyBadge, CAI_STORE.status.latencyMs + " ms");
      txt(els.schemaBadge, CAI_STORE.status.schemaVersion || "—");

      fillClauseSelect(env);
      renderAnalysis(CAI_STORE.analysis.analysis);
      status("Analyze OK • cid=" + (CAI_STORE.status.cid || "—") + " cache=" + (CAI_STORE.status.xcache || "—"));
    } catch (e) { status("✖ Analyze error: " + (e && e.message ? e.message : e)); }
  }

  async function doDraft() {
    var analysis = CAI_STORE.analysis.analysis;
    var text = val(els.clause) || "";
    if (!analysis && !text.trim()) { status("⚠️ Nothing to draft. Paste text or run Analyze."); return; }
    status("Drafting…");
    try {
      var input = analysis ? { analysis: analysis, mode: "friendly" } : { text: text, mode: "friendly" };
      var r = await apiGptDraft(input);
      if (!r.ok) { status("Draft HTTP " + r.status); return; }
      var env = (r.json && (r.json.data || r.json)) || {};
      var draft = env.draft_text || env.draft || "";
      setVal(els.draft, draft);
      window.LAST_DRAFT = draft;
      enableDraftApply(!!draft);
      status(draft ? "Draft OK" : "Draft empty");
    } catch (e) { status("✖ Draft error: " + (e && e.message ? e.message : e)); }
  }

  async function doSuggest() {
    if (!CAI_STORE.analysis || !CAI_STORE.analysis.clauses || !CAI_STORE.analysis.clauses.length) {
      status("⚠️ Run Analyze (doc) first");
      return;
    }
    var clauseId = val(els.sugSelect) || "";
    var mode = val(els.sugMode) || "friendly";
    var full = await readWholeDoc();
    status("Suggesting edits…");
    try {
      var r = await apiSuggestEdits({ text: full, clause: clauseId, mode: mode, top_k: 3 });
      if (!r.ok) { status("Suggest HTTP " + r.status); return; }
      var payload = r.json || {};
      var list = (payload.data && payload.data.suggestions) || payload.suggestions || [];
      renderSuggestions(list);
      try { window.CAI_renderSuggestions(list); } catch (_) {}
      status("Suggest OK (" + list.length + ")");
    } catch (e) { status("✖ Suggest error: " + (e && e.message ? e.message : e)); }
  }

  async function doAnnotate() {
    var analysis = CAI_STORE.analysis.analysis || null;
    if (!analysis) { status("⚠️ Analyze first."); return; }
    var thr = (val(els.riskThreshold) || CAI_STORE.settings.riskThreshold || "high").toLowerCase();
    var thrOrd = _riskOrd(thr);

    var full = await readWholeDoc();
    var items = Array.isArray(analysis.findings) ? analysis.findings : [];
    var risky = items.filter(function (f) { return _riskOrd(f && (f.risk || f.risk_level)) >= thrOrd; });
    if (!window.Word || !Word.run) { status("⚠️ Word API not available"); return; }

    try {
      await Word.run(function (ctx) {
        try {
          var comments = ctx.document.body.comments; comments.load("items");
        } catch (_) {}
        return ctx.sync().then(function () {
          try {
            if (comments && comments.items && comments.items.length) {
              comments.items.forEach(function (c) { try { c.delete(); } catch (_) {} });
            }
          } catch (_) {}
          return ctx.sync();
        });
      });

      for (var i = 0; i < risky.length; i++) {
        var f = risky[i];
        var msg = (f && f.code ? ("[" + f.code + "] ") : "") + (f && f.message ? f.message : "Issue") + (f && (f.risk || f.risk_level) ? (" — risk:" + (f.risk || f.risk_level)) : "");
        await addCommentAtSpan(full, f && f.span, msg);
      }
      status("Annotated (" + risky.length + ")");
    } catch (e) { status("✖ Annotate failed: " + (e && e.message ? e.message : e)); }
  }

  function addCommentAtSpan(fullText, span, message) {
    if (!window.Word || !Word.run) return Promise.resolve();
    var snippet = "";
    try {
      if (fullText && typeof fullText === "string" && span && typeof span.start === "number" && typeof span.length === "number") {
        snippet = fullText.substr(span.start, Math.min(span.length, 64));
      }
    } catch (_) {}
    return Word.run(function (ctx) {
      var body = ctx.document.body;
      var found = snippet ? body.search(snippet, { matchCase: false, matchWholeWord: false, ignorePunct: true, ignoreSpace: true }) : null;
      if (found) found.load("items");
      return ctx.sync().then(function () {
        var rng = null;
        if (found && found.items && found.items.length) rng = found.items[0];
        else rng = ctx.document.getSelection();
        try { rng.insertComment(String(message || "Contract AI")); } catch (_) {}
        return ctx.sync();
      });
    });
  }

  async function doQARecheck() {
    var full = await readWholeDoc();
    status("QA recheck…");
    try {
      var r = await apiQARecheck(full, []);
      if (!r.ok) { status("QA HTTP " + r.status); return; }
      var payload = r.json || {};
      var env = (payload && (payload.data || payload)) || {};
      var d = (env && (env.deltas || env)) || {};
      var scoreDelta = d.score_delta || 0;
      var riskDelta = d.risk_delta || 0;
      var badge = "Δ: s" + (scoreDelta >= 0 ? "+" : "") + (scoreDelta || 0) +
        " r" + (riskDelta >= 0 ? "+" : "") + (riskDelta || 0) +
        " " + (d.status_from || "") + "→" + (d.status_to || "");
      txt(els.qaDeltaBadge, badge);

      var res = (env && env.residual_risks) || [];
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
    } catch (e) { status("✖ QA error: " + (e && e.message ? e.message : e)); }
  }

  // ===== Wiring =====

  function wire() {
    els.backend = $("backendInput");
    els.btnSave = $("btnSave");
    els.btnTest = $("btnTest");
    els.buildInfo = $("buildInfo");
    els.connBadge = $("connBadge");
    els.officeBadge = $("officeBadge");
    els.cidBadge = $("cidBadge");
    els.xcacheBadge = $("xcacheBadge");
    els.latencyBadge = $("latencyBadge");
    els.schemaBadge = $("schemaBadge");
    els.doctorToggle = $("doctorToggle");
    els.doctorPanel = $("doctorPanel");
    els.doctorReqList = $("doctorReqList");
    els.doctorCid = $("doctorCid");
    els.doctorLatency = $("doctorLatency");
    els.doctorPayload = $("doctorPayload");

    els.clause = $("originalClause");
    els.analyzeBtn = $("analyzeBtn");
    els.draftBtn = $("draftBtn");
    els.copyBtn = $("copyResultBtn");
    els.useSel = $("useSelection");
    els.useDoc = $("useWholeDoc");
    els.btnInsert = $("btnInsertIntoWord");

    els.btnAnalyzeDoc = $("btnAnalyzeDoc");
    els.btnAnnotate = $("btnAnnotate");
    els.btnQARecheck = $("btnQARecheck");
    els.btnClearAnnots = $("btnClearAnnots");
    els.qaDeltaBadge = $("qaDeltaBadge");
    els.qaResiduals = $("qaResiduals");
    els.qaResidualList = $("qaResidualList");
    els.riskThreshold = $("riskThreshold");

    els.badgeScore = $("scoreBadge");
    els.badgeRisk = $("riskBadge");
    els.badgeStatus = $("statusBadge");
    els.badgeSev = $("severityBadge");

    els.resClauseType = $("resClauseType");
    els.resFindingsCount = $("resFindingsCount");
    els.findingsList = $("findingsList");
    els.recsList = $("recsList");
    els.toggleRaw = $("toggleRaw");
    els.rawJson = $("rawJson");

    els.sugSelect = $("cai-clause-select");
    els.sugMode = $("cai-mode");
    els.sugBtn = $("cai-btn-suggest");
    els.sugList = $("cai-suggest-list");

    els.draft = $("draftBox");
    els.btnPreview = $("btnPreview");
    els.btnApply = $("btnApply");
    els.btnAcceptAll = $("acceptAllBtn");
    els.btnRejectAll = $("rejectAllBtn");

    els.console = $("console");

    if (els.buildInfo) {
      try {
        var src = _manifestSrc();
        els.buildInfo.textContent = "Build: " + BUILD + " • " + src;
      } catch (_) { els.buildInfo.textContent = "Build: " + BUILD; }
    }

    // Fill backend input from LS (canonical, then legacy), fallback to HTTPS default
    try {
      var v = readLS(LS_KEY) || readLS(LS_KEY_OLD) || "https://127.0.0.1:9443";
      if (els.backend) els.backend.value = v;
    } catch (_) {}

    if (els.btnSave) els.btnSave.addEventListener("click", function () {
      var v = backend(); if (!v) { status("⚠️ Enter backend URL first"); return; }
      writeLS(LS_KEY, v); status("Saved: " + v);
    });

    if (els.btnTest) els.btnTest.addEventListener("click", function () { doHealthFlow(); });

    if (els.analyzeBtn) els.analyzeBtn.addEventListener("click", function () { doAnalyze(false); });
    if (els.btnAnalyzeDoc) els.btnAnalyzeDoc.addEventListener("click", function () { doAnalyze(true); });

    if (els.useSel) els.useSel.addEventListener("click", async function () { var t = await readSelection(); setVal(els.clause, t); status("Selection copied."); });
    if (els.useDoc) els.useDoc.addEventListener("click", async function () { var t = await readWholeDoc(); setVal(els.clause, t); status("Whole document copied."); });

    if (els.draftBtn) els.draftBtn.addEventListener("click", function () { doDraft(); });
    if (els.copyBtn) els.copyBtn.addEventListener("click", function () {
      try { navigator.clipboard && navigator.clipboard.writeText(val(els.draft) || ""); status("Draft copied to clipboard"); } catch (_) {}
    });

    if (els.sugBtn) els.sugBtn.addEventListener("click", function () { doSuggest(); });

    if (els.toggleRaw) els.toggleRaw.addEventListener("click", function () {
      if (!els.rawJson) return;
      var s = window.getComputedStyle(els.rawJson).display;
      els.rawJson.style.display = (s === "none" ? "block" : "none");
    });

    if (els.btnInsert) els.btnInsert.addEventListener("click", async function () {
      try {
        var t = val(els.draft).trim();
        if (!t) { status("Draft empty"); return; }
        await insertPlain(t);
        status("Inserted into Word (plain)");
      } catch (e) { status("✖ Insert failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnApply) els.btnApply.addEventListener("click", async function () {
      try {
        var t = val(els.draft).trim(); if (!t) { status("Draft empty"); return; }
        await applyTracked(t, "Contract AI — applied draft");
        enableDraftApply(true);
        status("Applied as tracked changes.");
        try {
          var now = new Date().toISOString();
          var norm = normalizeText(val(els.clause) || "");
          var docHash = await sha256Hex(norm + "|local");
          var ev = {
            schema_ver: "1",
            event_id: "ev-" + Date.now(),
            ts: now,
            action: "applied",
            user: "local",
            doc_id: docHash,
            clause_id: val(els.sugSelect) || null,
            mode: val(els.sugMode) || "friendly",
            ui_latency_ms: CAI_STORE.status.latencyMs || null,
            client: { cid: CAI_STORE.status.cid || "", panel_build: BUILD }
          };
          apiLearningLog([ev]).catch(function () {});
        } catch (_) {}
      } catch (e) { status("✖ Apply failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnPreview) els.btnPreview.addEventListener("click", function () {
      var o = val(els.clause) || "", d = val(els.draft) || "";
      if (!o || !d) { status("Provide original and draft for diff."); return; }
      status("Diff ready (console). orig.len=" + o.length + " draft.len=" + d.length);
    });

    if (els.btnAcceptAll) els.btnAcceptAll.addEventListener("click", async function () {
      try { await acceptAll(); status("Accepted all changes."); } catch (e) { status("✖ Accept failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnRejectAll) els.btnRejectAll.addEventListener("click", async function () {
      try { await rejectAll(); status("Rejected all changes."); } catch (e) { status("✖ Reject failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnAnnotate) els.btnAnnotate.addEventListener("click", function () { doAnnotate(); });
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
    wire();
    ensureOfficeBadge();
    status("📦 Bundle ready (" + BUILD + "). Set backend and click Test.");
    try { window.__CAI_WIRED__ = "ready"; } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", boot, { once: true });

  window.addEventListener("error", function (e) {
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[JS ERROR] " + (e.message || e.error || e) + "\n")); n.scrollTop = n.scrollHeight; } } catch (_) {}
  });
  window.addEventListener("unhandledrejection", function (e) {
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[PROMISE REJECTION] " + (e.reason && (e.reason.message || e.reason)) + "\n")); n.scrollTop = n.scrollHeight; } } catch (_) {}
  });

})();
