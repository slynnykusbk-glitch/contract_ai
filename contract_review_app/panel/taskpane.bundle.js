(() => {
  // assets/store.ts
  var DEFAULT_API_KEY = "";
  var DEFAULT_SCHEMA = "1.4";
  var ADD_COMMENTS_KEY = "cai-comment-on-analyze";
  function ensureDefaults() {
    try {
      if (localStorage.getItem("api_key") === null) {
        localStorage.setItem("api_key", DEFAULT_API_KEY);
      }
      if (localStorage.getItem("schema_version") === null) {
        localStorage.setItem("schema_version", DEFAULT_SCHEMA);
      }
      if (localStorage.getItem(ADD_COMMENTS_KEY) === null) {
        localStorage.setItem(ADD_COMMENTS_KEY, "1");
      }
    } catch {
    }
  }
  ensureDefaults();
  function getApiKeyFromStore() {
    try {
      return localStorage.getItem("api_key") || DEFAULT_API_KEY;
    } catch {
      return DEFAULT_API_KEY;
    }
  }
  function setApiKey(k) {
    try {
      localStorage.setItem("api_key", k);
    } catch {
    }
  }
  function getSchemaFromStore() {
    try {
      return localStorage.getItem("schema_version") || DEFAULT_SCHEMA;
    } catch {
      return DEFAULT_SCHEMA;
    }
  }
  function setSchemaVersion(v) {
    try {
      localStorage.setItem("schema_version", v);
    } catch {
    }
  }
  function getAddCommentsFlag() {
    try {
      const v = localStorage.getItem(ADD_COMMENTS_KEY);
      if (v === null) {
        localStorage.setItem(ADD_COMMENTS_KEY, "1");
        return true;
      }
      return v !== "0";
    } catch {
      return true;
    }
  }
  function setAddCommentsFlag(v) {
    try {
      localStorage.setItem(ADD_COMMENTS_KEY, v ? "1" : "0");
    } catch {
    }
  }
  var root = typeof globalThis !== "undefined" ? globalThis : window;
  root.CAI = root.CAI || {};
  root.CAI.Store = root.CAI.Store || {};
  root.CAI.Store.setApiKey = setApiKey;
  root.CAI.Store.setSchemaVersion = setSchemaVersion;
  root.CAI.Store.get = () => ({ apiKey: getApiKeyFromStore(), schemaVersion: getSchemaFromStore() });
  root.CAI.Store.DEFAULT_BASE = root.CAI.Store.DEFAULT_BASE || "https://localhost:9443";

  // assets/api-client.ts
  function parseFindings(resp) {
    var _a2, _b, _c, _d;
    const arr = (_d = (_c = (_b = (_a2 = resp == null ? void 0 : resp.analysis) == null ? void 0 : _a2.findings) != null ? _b : resp == null ? void 0 : resp.findings) != null ? _c : resp == null ? void 0 : resp.issues) != null ? _d : [];
    return Array.isArray(arr) ? arr.filter(Boolean) : [];
  }
  window.parseFindings = parseFindings;
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
  async function postJSON(path, body) {
    const url = base() + path;
    const headers = { "Content-Type": "application/json" };
    const schema = getSchemaFromStore() || "1.4";
    headers["x-schema-version"] = schema;
    const key = getApiKeyFromStore();
    if (key) headers["x-api-key"] = key;
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body || {}),
      credentials: "include"
    });
    const json = await resp.json().catch(() => ({}));
    return { resp, json };
  }
  window.postJson = postJSON;
  async function postRedlines(before_text, after_text) {
    return postJSON("/api/panel/redlines", { before_text, after_text });
  }

  // assets/dedupe.ts
  function normalizeText(s) {
    if (!s) return "";
    return s.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\u00A0/g, " ").replace(/[ \t]+/g, " ").trim();
  }
  function severityRank(s) {
    const m = (s || "").toLowerCase();
    return m === "high" ? 3 : m === "medium" ? 2 : 1;
  }
  function dedupeFindings(findings) {
    const map = /* @__PURE__ */ new Map();
    let invalid = 0, dupes = 0;
    for (const f of findings || []) {
      const snippet = normalizeText(f.snippet || "");
      const start = typeof f.start === "number" ? f.start : void 0;
      const end = typeof f.end === "number" ? f.end : start !== void 0 ? start + snippet.length : void 0;
      if (typeof start !== "number" || typeof end !== "number" || end <= start || end - start > 1e4) {
        invalid++;
        continue;
      }
      const key = `${f.rule_id || ""}|${start}|${end}|${snippet}`;
      const ex = map.get(key);
      if (!ex || severityRank(f.severity) > severityRank(ex.severity)) {
        map.set(key, { ...f, snippet, start, end });
      } else {
        dupes++;
      }
    }
    const res = Array.from(map.values());
    console.log("panel:annotate", `dedupe dropped ${invalid} invalid, ${dupes} duplicates`);
    return res;
  }

  // assets/notifier.ts
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

  // assets/office.ts
  async function getWholeDocText() {
    return await Word.run(async (ctx) => {
      const body = ctx.document.body;
      body.load("text");
      await ctx.sync();
      return (body.text || "").trim();
    });
  }

  // assets/taskpane.ts
  var oe = globalThis.OfficeExtension;
  var gg = globalThis;
  var _a;
  if (oe && oe.config) {
    const env = (_a = gg.__ENV__) != null ? _a : typeof process !== "undefined" ? "development" : "production";
    const isProd = env === "production";
    if (!isProd || gg.__ENABLE_EXTENDED_LOGS__) {
      oe.config.extendedErrorLogging = true;
    }
  }
  function logRichError(e, tag = "Word") {
    try {
      const di = e && e.debugInfo || {};
      console.error(`[${tag}] RichApi error`, {
        code: e.code,
        message: e.message,
        errorLocation: di.errorLocation,
        statements: di.statements,
        traceMessages: di.traceMessages,
        inner: di.innerError
      });
    } catch {
    }
  }
  function parseFindings2(resp) {
    const arr = parseFindings(resp) || [];
    return arr.filter((f) => f && f.rule_id && f.snippet).map((f) => ({ ...f, clause_type: f.clause_type || "Unknown" })).filter((f) => f.clause_type);
  }
  var g = globalThis;
  g.parseFindings = g.parseFindings || parseFindings2;
  g.applyMetaToBadges = g.applyMetaToBadges || applyMetaToBadges;
  g.getApiKeyFromStore = g.getApiKeyFromStore || getApiKeyFromStore;
  g.getSchemaFromStore = g.getSchemaFromStore || getSchemaFromStore;
  g.logRichError = g.logRichError || logRichError;
  g.getWholeDocText = g.getWholeDocText || getWholeDocText;
  var Q = {
    proposed: 'textarea#proposedText, textarea#draftText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
    original: 'textarea#originalClause, textarea#originalText, textarea[name="original"], textarea[data-role="original-clause"]'
  };
  var lastCid = "";
  var analyzeBound = false;
  function updateStatusChip(schema, cid) {
    const el = document.getElementById("status-chip");
    if (!el) return;
    const s = (schema != null ? schema : getSchemaFromStore()) || "\u2014";
    const c = (cid != null ? cid : lastCid) || "\u2014";
    el.textContent = `schema: ${s} | cid: ${c}`;
  }
  function enableAnalyze() {
    if (analyzeBound) return;
    bindClick("#btnAnalyze", doAnalyze);
    const btn = document.getElementById("btnAnalyze");
    if (btn) btn.disabled = false;
    analyzeBound = true;
  }
  function getBackend() {
    try {
      return (localStorage.getItem("backend.url") || localStorage.getItem("backendUrl") || "https://localhost:9443").replace(/\/+$/, "");
    } catch {
      return "https://localhost:9443";
    }
  }
  function onSaveBackend() {
    var _a2;
    const inp = document.getElementById("backendUrl");
    const val = (_a2 = inp == null ? void 0 : inp.value) == null ? void 0 : _a2.trim();
    if (val) {
      try {
        localStorage.setItem("backend.url", val);
        localStorage.setItem("backendUrl", val);
      } catch {
      }
    }
    location.reload();
  }
  function ensureHeaders() {
    var _a2, _b, _c;
    try {
      let apiKey = getApiKeyFromStore();
      let schema = getSchemaFromStore();
      const warn = document.getElementById("hdrWarn");
      const host = (_b = (_a2 = globalThis == null ? void 0 : globalThis.location) == null ? void 0 : _a2.hostname) != null ? _b : "";
      const isDev = host === "localhost" || host === "127.0.0.1";
      if (isDev) {
        if (!apiKey) {
          apiKey = "local-test-key-123";
          setApiKey(apiKey);
        }
        if (!schema) {
          const envSchema = (globalThis == null ? void 0 : globalThis.SCHEMA_VERSION) || typeof process !== "undefined" && ((_c = process.env) == null ? void 0 : _c.SCHEMA_VERSION) || "1.4";
          schema = String(envSchema);
          setSchemaVersion(schema);
        }
      }
      if (warn) {
        if (!apiKey && !schema && !isDev) {
          warn.style.display = "";
        } else {
          warn.style.display = "none";
        }
      }
      if (!apiKey || !schema) {
        console.warn("missing headers", { apiKey: !!apiKey, schema: !!schema });
      }
    } catch {
    }
    return true;
  }
  function slot(id, role) {
    return document.querySelector(`[data-role="${role}"]`) || document.getElementById(id);
  }
  function getRiskThreshold() {
    var _a2;
    const sel = document.getElementById("selectRiskThreshold") || document.getElementById("riskThreshold");
    const v = (_a2 = sel == null ? void 0 : sel.value) == null ? void 0 : _a2.toLowerCase();
    return v === "low" || v === "medium" || v === "high" ? v : "medium";
  }
  function isAddCommentsOnAnalyzeEnabled() {
    const val = getAddCommentsFlag();
    try {
      const doc = globalThis.document;
      const cb = (doc == null ? void 0 : doc.getElementById("cai-comment-on-analyze")) || (doc == null ? void 0 : doc.getElementById("chkAddCommentsOnAnalyze"));
      if (cb) cb.checked = val;
      return cb ? !!cb.checked : val;
    } catch {
      return val;
    }
  }
  function setAddCommentsOnAnalyze(val) {
    setAddCommentsFlag(val);
  }
  function isDryRunAnnotateEnabled() {
    const cb = document.getElementById("cai-dry-run-annotate");
    return cb ? !!cb.checked : false;
  }
  function filterByThreshold(list, thr) {
    const min = severityRank(thr);
    return (list || []).filter((f) => f && f.rule_id && f.snippet).map((f) => ({ ...f, clause_type: f.clause_type || "Unknown" })).filter((f) => severityRank(f.severity) >= min);
  }
  function buildLegalComment(f) {
    var _a2;
    if (!f || !f.rule_id || !f.snippet) {
      console.warn("buildLegalComment: missing required fields", f);
      return "";
    }
    const sev = (f.severity || "info").toUpperCase();
    const rid = f.rule_id;
    const ct = f.clause_type ? ` (${f.clause_type})` : "";
    const advice = f.advice || "\u2014";
    const law = Array.isArray(f.law_refs) && f.law_refs.length ? f.law_refs.join("; ") : "\u2014";
    const conflict = Array.isArray(f.conflict_with) && f.conflict_with.length ? f.conflict_with.join("; ") : "\u2014";
    const fix = ((_a2 = f.suggestion) == null ? void 0 : _a2.text) || "\u2014";
    const citations = Array.isArray(f.citations) && f.citations.length ? `
Citations: ${f.citations.join("; ")}` : "";
    return `[${sev}] ${rid}${ct}
Reason: ${advice}
Law: ${law}
Conflict: ${conflict}${citations}
Suggested fix: ${fix}`;
  }
  function nthOccurrenceIndex(hay, needle, startPos) {
    if (!needle) return 0;
    let idx = -1, n = 0;
    const bound = typeof startPos === "number" ? Math.max(0, startPos) : Number.MAX_SAFE_INTEGER;
    while ((idx = hay.indexOf(needle, idx + 1)) !== -1 && idx < bound) n++;
    return n;
  }
  function buildParagraphIndex(paragraphs) {
    const starts = [];
    const texts = [];
    let pos = 0;
    for (const p of paragraphs) {
      const t = normalizeText(p);
      starts.push(pos);
      texts.push(t);
      pos += t.length + 1;
    }
    return { starts, texts };
  }
  async function mapFindingToRange(f) {
    const last = window.__lastAnalyzed || "";
    const base2 = normalizeText(last);
    const snippet = normalizeText(f.snippet || "");
    const occIdx = nthOccurrenceIndex(base2, snippet, f.start);
    try {
      return await Word.run(async (ctx) => {
        const body = ctx.document.body;
        const searchRes = body.search(snippet, { matchCase: false, matchWholeWord: false });
        searchRes.load("items");
        await ctx.sync();
        const items = searchRes.items || [];
        return items[Math.min(occIdx, Math.max(0, items.length - 1))] || null;
      });
    } catch (e) {
      logRichError(e, "findings");
      console.warn("mapFindingToRange fail", e);
      return null;
    }
  }
  async function annotateFindingsIntoWord(findings) {
    const base2 = normalizeText(window.__lastAnalyzed || "");
    const deduped = dedupeFindings(findings || []);
    const sorted = deduped.slice().sort((a, b) => {
      var _a2, _b;
      return ((_a2 = b.end) != null ? _a2 : 0) - ((_b = a.end) != null ? _b : 0);
    });
    const todo = [];
    let lastStart = Number.POSITIVE_INFINITY;
    let skipped = 0;
    for (const f of sorted) {
      if (!f || !f.rule_id || !f.snippet) {
        skipped++;
        continue;
      }
      const snippet = f.snippet;
      const end = typeof f.end === "number" ? f.end : typeof f.start === "number" ? f.start + snippet.length : void 0;
      if (typeof end === "number" && end > lastStart) {
        skipped++;
        continue;
      }
      todo.push(f);
      if (typeof f.start === "number") lastStart = f.start;
    }
    if (skipped) notifyWarn(`Skipped ${skipped} overlaps/invalid`);
    notifyOk(`Will insert: ${todo.length}`);
    const items = todo.map((f) => {
      const raw = f.snippet || "";
      const norm = normalizeText(raw);
      const occIdx = nthOccurrenceIndex(base2, norm, f.start);
      return {
        raw,
        norm,
        msg: buildLegalComment(f),
        rule_id: f.rule_id,
        occIdx,
        normalized_fallback: normalizeText(f.normalized_snippet || "")
      };
    });
    const searchOpts = { matchCase: false, matchWholeWord: false };
    let inserted = 0;
    for (const it of items) {
      await Word.run(async (ctx) => {
        const body = ctx.document.body;
        let target = null;
        const sRaw = body.search(it.raw, searchOpts);
        sRaw.load("items");
        await ctx.sync();
        const pick = (coll, occ) => {
          const arr = (coll == null ? void 0 : coll.items) || [];
          if (!arr.length) return null;
          return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
        };
        target = pick(sRaw, it.occIdx);
        if (!target) {
          const fb = it.normalized_fallback && it.normalized_fallback !== it.norm ? it.normalized_fallback : it.norm;
          if (fb && fb.trim()) {
            const sNorm = body.search(fb, searchOpts);
            sNorm.load("items");
            await ctx.sync();
            target = pick(sNorm, it.occIdx);
          }
        }
        if (!target) {
          const token = (() => {
            const tks = it.raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter((x) => x.length >= 12);
            if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
            return null;
          })();
          if (token) {
            const sTok = body.search(token, searchOpts);
            sTok.load("items");
            await ctx.sync();
            target = pick(sTok, 0);
          }
        }
        if (target) {
          if (isDryRunAnnotateEnabled()) {
            try {
              target.select();
            } catch {
            }
          } else if (it.msg) {
            target.insertComment(it.msg);
          }
          inserted++;
        } else {
          console.warn("[annotate] no match for snippet", { rid: it.rule_id, snippet: it.raw.slice(0, 120) });
        }
        await ctx.sync();
      }).catch((e) => {
        logRichError(e, "annotate");
        console.warn("annotate run fail", e == null ? void 0 : e.code, e == null ? void 0 : e.message, e == null ? void 0 : e.debugInfo);
      });
    }
    console.log("panel:annotate", {
      total: findings.length,
      deduped: deduped.length,
      skipped_overlaps: skipped,
      will_annotate: todo.length,
      inserted
    });
    return inserted;
  }
  g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;
  async function onClearAnnots() {
    try {
      await Word.run(async (ctx) => {
        const body = ctx.document.body;
        const cmts = ctx.document.comments;
        cmts.load("items");
        await ctx.sync();
        for (const c of cmts.items) {
          try {
            c.delete();
          } catch {
          }
        }
        try {
          body.font.highlightColor = "NoColor";
        } catch {
        }
        await ctx.sync();
      });
      notifyOk("Annotations cleared");
    } catch (e) {
      logRichError(e, "annotate");
      notifyWarn("Failed to clear annotations");
    }
  }
  async function applyOpsTracked(ops) {
    let cleaned = (ops || []).filter((o) => typeof o.start === "number" && typeof o.end === "number" && o.end > o.start).sort((a, b) => a.start - b.start);
    let lastEnd = -1;
    cleaned = cleaned.filter((o) => {
      if (o.start < lastEnd) return false;
      lastEnd = o.end;
      return true;
    });
    if (!cleaned.length) return;
    const last = window.__lastAnalyzed || "";
    await Word.run(async (ctx) => {
      const body = ctx.document.body;
      ctx.document.trackRevisions = true;
      const searchOpts = { matchCase: false, matchWholeWord: false };
      const pick = (coll, occ) => {
        const arr = (coll == null ? void 0 : coll.items) || [];
        if (!arr.length) return null;
        return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
      };
      for (const op of cleaned) {
        const snippet = last.slice(op.start, op.end);
        const occIdx = (() => {
          let idx = -1, n = 0;
          while ((idx = last.indexOf(snippet, idx + 1)) !== -1 && idx < op.start) n++;
          return n;
        })();
        let target = null;
        if (op.context_before || op.context_after) {
          const searchText = `${op.context_before || ""}${snippet}${op.context_after || ""}`;
          const sFull = body.search(searchText, searchOpts);
          sFull.load("items");
          await ctx.sync();
          const fullRange = pick(sFull, occIdx);
          if (fullRange) {
            const inner = fullRange.search(snippet, searchOpts);
            inner.load("items");
            await ctx.sync();
            target = pick(inner, 0);
          }
        }
        if (!target) {
          const found = body.search(snippet, searchOpts);
          found.load("items");
          await ctx.sync();
          target = pick(found, occIdx);
        }
        if (!target) {
          const token = (() => {
            const tks = snippet.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter((x) => x.length >= 12);
            if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
            return null;
          })();
          if (token) {
            const sTok = body.search(token, searchOpts);
            sTok.load("items");
            await ctx.sync();
            target = pick(sTok, 0);
          }
        }
        if (target) {
          target.insertText(op.replacement, "Replace");
          const comment = op.rationale || op.source || "AI edit";
          try {
            target.insertComment(comment);
          } catch {
          }
        } else {
          console.warn("[applyOpsTracked] match not found", { snippet, occIdx });
        }
        await ctx.sync();
      }
    });
  }
  g.applyOpsTracked = g.applyOpsTracked || applyOpsTracked;
  async function highlightFinding(f) {
    const base2 = normalizeText(window.__lastAnalyzed || "");
    const raw = (f == null ? void 0 : f.snippet) || "";
    const norm = normalizeText(raw);
    const occIdx = nthOccurrenceIndex(base2, norm, f.start);
    const searchOpts = { matchCase: false, matchWholeWord: false };
    await Word.run(async (ctx) => {
      const body = ctx.document.body;
      let target = null;
      const pick = (coll, occ) => {
        const arr = (coll == null ? void 0 : coll.items) || [];
        if (!arr.length) return null;
        return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
      };
      const sRaw = body.search(raw, searchOpts);
      sRaw.load("items");
      await ctx.sync();
      target = pick(sRaw, occIdx);
      if (!target) {
        const fb = f.normalized_snippet && f.normalized_snippet !== norm ? f.normalized_snippet : norm;
        if (fb && fb.trim()) {
          const sNorm = body.search(fb, searchOpts);
          sNorm.load("items");
          await ctx.sync();
          target = pick(sNorm, occIdx);
        }
      }
      if (!target) {
        const token = (() => {
          const tks = raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter((x) => x.length >= 12);
          if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
          return null;
        })();
        if (token) {
          const sTok = body.search(token, searchOpts);
          sTok.load("items");
          await ctx.sync();
          target = pick(sTok, 0);
        }
      }
      if (target) {
        try {
          target.select();
        } catch {
        }
      }
      await ctx.sync();
    });
  }
  async function navigateFinding(dir) {
    var _a2;
    const arr = window.__findings || [];
    if (!arr.length) return;
    const w = window;
    w.__findingIdx = ((_a2 = w.__findingIdx) != null ? _a2 : 0) + dir;
    if (w.__findingIdx < 0) w.__findingIdx = arr.length - 1;
    if (w.__findingIdx >= arr.length) w.__findingIdx = 0;
    const list = document.getElementById("findingsList");
    if (list) {
      const items = Array.from(list.querySelectorAll("li"));
      items.forEach((li, i) => {
        li.classList.toggle("active", i === w.__findingIdx);
      });
      const act = items[w.__findingIdx];
      if (act) act.scrollIntoView({ block: "nearest" });
    }
    try {
      await highlightFinding(arr[w.__findingIdx]);
    } catch {
    }
  }
  function onPrevIssue() {
    navigateFinding(-1);
  }
  function onNextIssue() {
    navigateFinding(1);
  }
  function renderAnalysisSummary(json) {
    var _a2, _b, _c, _d;
    const clauseType = ((_a2 = json == null ? void 0 : json.summary) == null ? void 0 : _a2.clause_type) || ((_b = json == null ? void 0 : json.meta) == null ? void 0 : _b.clause_type) || (json == null ? void 0 : json.doc_type) || "\u2014";
    const findings = Array.isArray(json == null ? void 0 : json.findings) ? json.findings : [];
    const recs = Array.isArray(json == null ? void 0 : json.recommendations) ? json.recommendations : [];
    const thr = getRiskThreshold();
    const visibleFindings = filterByThreshold(findings, thr);
    const visible = visibleFindings.length;
    const hidden = findings.length - visible;
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    setText("clauseTypeOut", String(clauseType));
    setText("resFindingsCount", String(findings.length));
    setText("visibleHiddenOut", `${visible} / ${hidden}`);
    const fCont = document.getElementById("findingsList");
    if (fCont) {
      fCont.innerHTML = "";
      for (const f of findings) {
        const li = document.createElement("li");
        const title = (f == null ? void 0 : f.title) || ((_c = f == null ? void 0 : f.finding) == null ? void 0 : _c.title) || (f == null ? void 0 : f.rule_id) || "Issue";
        const snippet = (f == null ? void 0 : f.snippet) || ((_d = f == null ? void 0 : f.evidence) == null ? void 0 : _d.text) || "";
        li.textContent = snippet ? `${title}: ${snippet}` : String(title);
        fCont.appendChild(li);
      }
    }
    const rCont = document.getElementById("recsList");
    if (rCont) {
      rCont.innerHTML = "";
      for (const r of recs) {
        const li = document.createElement("li");
        li.textContent = (r == null ? void 0 : r.text) || (r == null ? void 0 : r.advice) || (r == null ? void 0 : r.message) || "Recommendation";
        rCont.appendChild(li);
      }
    }
    const rb = document.getElementById("resultsBlock");
    if (rb) rb.style.removeProperty("display");
  }
  function renderResults(res) {
    const clause = slot("resClauseType", "clause-type");
    if (clause) clause.textContent = (res == null ? void 0 : res.clause_type) || "\u2014";
    const findingsArr = parseFindings2(res);
    window.__findings = findingsArr;
    window.__findingIdx = 0;
    const findingsList = slot("findingsList", "findings");
    if (findingsList) {
      findingsList.innerHTML = "";
      findingsArr.forEach((f) => {
        const li = document.createElement("li");
        li.textContent = typeof f === "string" ? f : JSON.stringify(f);
        findingsList.appendChild(li);
      });
    }
    const recoArr = Array.isArray(res == null ? void 0 : res.recommendations) ? res.recommendations : [];
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
    if (pre) pre.textContent = JSON.stringify(res != null ? res : {}, null, 2);
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
    if (el) el.textContent = `Office: ${txt != null ? txt : "\u2014"}`;
  }
  function $(sel) {
    return document.querySelector(sel);
  }
  async function onUseWholeDoc() {
    var _a2;
    const src = $(Q.original);
    const raw = await getWholeDocText();
    const text = normalizeText(raw || "");
    if (src) {
      src.value = text;
      src.dispatchEvent(new Event("input", { bubbles: true }));
    }
    window.__lastAnalyzed = text;
    (_a2 = window.toast) == null ? void 0 : _a2.call(window, "Whole doc loaded");
  }
  async function onSuggestEdit(ev) {
    var _a2, _b, _c;
    try {
      const dst = $(Q.proposed);
      const base2 = window.__lastAnalyzed || normalizeText(await getWholeDocText());
      if (!base2) {
        notifyWarn("No document text");
        return;
      }
      const arr = window.__findings || [];
      const idx = (_a2 = window.__findingIdx) != null ? _a2 : 0;
      const finding = arr[idx];
      if (!finding) {
        notifyWarn("No active finding");
        return;
      }
      const clause = finding.snippet || "";
      const { json } = await postJSON("/api/gpt-draft", { cid: lastCid, clause, mode: "friendly" });
      const proposed = ((_c = (_b = json == null ? void 0 : json.proposed_text) != null ? _b : json == null ? void 0 : json.text) != null ? _c : "").toString();
      const w = window;
      w.__last = w.__last || {};
      w.__last["gpt-draft"] = { json };
      if (dst) {
        if (!dst.id) dst.id = "draftText";
        if (!dst.name) dst.name = "proposed";
        dst.dataset.role = "proposed-text";
        dst.value = proposed;
        dst.dispatchEvent(new Event("input", { bubbles: true }));
        notifyOk("Draft ready");
        onDraftReady(proposed);
      } else {
        notifyWarn("Proposed textarea not found");
        onDraftReady("");
      }
    } catch (e) {
      notifyWarn("Draft error");
      console.error(e);
      onDraftReady("");
    }
  }
  async function doHealth() {
    try {
      const prev = getSchemaFromStore();
      const resp = await fetch(`${getBackend()}/health`, { method: "GET" });
      const json = await resp.json().catch(() => ({}));
      const schema = resp.headers.get("x-schema-version") || (json == null ? void 0 : json.schema) || null;
      if (schema) {
        setSchemaVersion(schema);
        if (schema !== prev) {
          console.log(`schema: ${schema} (synced)`);
        }
      }
      setConnBadge(true);
      enableAnalyze();
      updateStatusChip(schema, null);
      try {
        applyMetaToBadges({
          cid: null,
          xcache: null,
          latencyMs: null,
          schema: schema || null,
          provider: (json == null ? void 0 : json.provider) || null,
          model: (json == null ? void 0 : json.model) || null,
          llm_mode: null,
          usage: null,
          status: (json == null ? void 0 : json.status) || null
        });
      } catch {
      }
      notifyOk(`Health: ${(json == null ? void 0 : json.status) || "ok"}${schema ? ` (schema ${schema})` : ""}`);
    } catch (e) {
      setConnBadge(false);
      notifyWarn("Health failed");
      console.error(e);
    }
  }
  async function doAnalyze() {
    const btn = document.getElementById("btnAnalyze");
    const busy = document.getElementById("busyBar");
    if (btn) btn.disabled = true;
    if (busy) busy.style.display = "";
    try {
      onDraftReady("");
      const cached = window.__lastAnalyzed;
      const base2 = cached && cached.trim() ? cached : normalizeText(await globalThis.getWholeDocText());
      if (!base2) {
        notifyErr("\u0412 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435 \u043D\u0435\u0442 \u0442\u0435\u043A\u0441\u0442\u0430");
        return;
      }
      ensureHeaders();
      window.__lastAnalyzed = base2;
      const orig = document.getElementById("originalText");
      if (orig) orig.value = base2;
      const { resp, json } = await postJSON("/api/analyze", { text: base2 });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const respSchema = resp.headers.get("x-schema-version");
      if (respSchema) setSchemaVersion(respSchema);
      if (json == null ? void 0 : json.schema) setSchemaVersion(json.schema);
      lastCid = resp.headers.get("x-cid") || "";
      updateStatusChip(null, lastCid);
      renderResults(json);
      renderAnalysisSummary(json);
      try {
        localStorage.setItem("last_analysis_json", JSON.stringify(json));
      } catch {
      }
      try {
        const all = globalThis.parseFindings(json);
        const thr = getRiskThreshold();
        const filtered = filterByThreshold(all, thr);
        if (isAddCommentsOnAnalyzeEnabled() && filtered.length) {
          await globalThis.annotateFindingsIntoWord(filtered);
        }
      } catch (e) {
        console.warn("auto-annotate after analyze failed", e);
      }
      (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
      notifyOk("Analyze OK");
    } catch (e) {
      notifyWarn("Analyze failed");
      console.error(e);
    } finally {
      if (btn) btn.disabled = false;
      if (busy) busy.style.display = "none";
    }
  }
  async function doQARecheck() {
    ensureHeaders();
    const text = await getWholeDocText();
    const { json } = await postJSON("/api/qa-recheck", { text, rules: {} });
    (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
    const ok = !(json == null ? void 0 : json.error);
    if (ok) {
      notifyOk("QA recheck OK");
    } else {
      const msg = (json == null ? void 0 : json.error) || (json == null ? void 0 : json.message) || "unknown";
      notifyErr(`QA recheck failed: ${msg}`);
    }
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
  async function onPreviewDiff() {
    var _a2, _b, _c, _d;
    try {
      const before = window.__lastAnalyzed || "";
      const after = (((_a2 = $(Q.proposed)) == null ? void 0 : _a2.value) || "").trim();
      if (!after) {
        notifyWarn("No draft to diff");
        return;
      }
      const diff = await postRedlines(before, after);
      const html = ((_b = diff == null ? void 0 : diff.json) == null ? void 0 : _b.html) || ((_c = diff == null ? void 0 : diff.json) == null ? void 0 : _c.diff_html) || ((_d = diff == null ? void 0 : diff.json) == null ? void 0 : _d.redlines) || "";
      const out = document.getElementById("diffOutput");
      const cont = document.getElementById("diffContainer");
      if (out && cont) {
        out.innerHTML = html || "";
        cont.style.display = html ? "block" : "none";
      }
    } catch (e) {
      notifyWarn("Diff failed");
      console.error(e);
    }
  }
  async function onApplyTracked() {
    var _a2, _b, _c, _d;
    try {
      const last = window.__last || {};
      const ops = ((_b = (_a2 = last["gpt-draft"]) == null ? void 0 : _a2.json) == null ? void 0 : _b.ops) || ((_d = (_c = last["suggest"]) == null ? void 0 : _c.json) == null ? void 0 : _d.ops) || [];
      if (!ops.length) {
        notifyWarn("No ops to apply");
        return;
      }
      await applyOpsTracked(ops);
      notifyOk("Applied ops");
    } catch (e) {
      notifyWarn("Insert failed");
      console.error(e);
    }
  }
  async function onAcceptAll() {
    var _a2, _b, _c, _d;
    try {
      const dst = $(Q.proposed);
      const proposed = ((dst == null ? void 0 : dst.value) || "").trim();
      if (!proposed) {
        (_a2 = window.toast) == null ? void 0 : _a2.call(window, "Nothing to accept");
        return;
      }
      const cid = (((_b = document.getElementById("cid")) == null ? void 0 : _b.textContent) || "").trim();
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
        range.insertText(proposed, Word.InsertLocation.replace);
        try {
          range.insertComment(link);
        } catch {
        }
        await ctx.sync();
      });
      (_c = window.toast) == null ? void 0 : _c.call(window, "Accepted into Word");
      console.log("[OK] Accepted into Word");
    } catch (e) {
      (_d = window.toast) == null ? void 0 : _d.call(window, "Accept failed");
      logRichError(e, "insertDraft");
      console.error(e);
    }
  }
  async function onRejectAll() {
    var _a2, _b;
    try {
      const dst = $(Q.proposed);
      if (dst) {
        dst.value = "";
        dst.dispatchEvent(new Event("input", { bubbles: true }));
        onDraftReady("");
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
      (_a2 = window.toast) == null ? void 0 : _a2.call(window, "Rejected");
      console.log("[OK] Rejected");
    } catch (e) {
      (_b = window.toast) == null ? void 0 : _b.call(window, "Reject failed");
      logRichError(e, "insertDraft");
      console.error(e);
    }
  }
  function wireUI() {
    var _a2;
    bindClick("#btnUseWholeDoc", onUseWholeDoc);
    bindClick("#btnTest", doHealth);
    bindClick("#btnQARecheck", doQARecheck);
    (_a2 = document.getElementById("btnSuggestEdit")) == null ? void 0 : _a2.addEventListener("click", onSuggestEdit);
    bindClick("#btnApplyTracked", onApplyTracked);
    bindClick("#btnAcceptAll", onAcceptAll);
    bindClick("#btnRejectAll", onRejectAll);
    bindClick("#btnPrevIssue", onPrevIssue);
    bindClick("#btnNextIssue", onNextIssue);
    bindClick("#btnPreviewDiff", onPreviewDiff);
    bindClick("#btnClearAnnots", onClearAnnots);
    bindClick("#btnSave", onSaveBackend);
    const cb = document.getElementById("cai-comment-on-analyze") || document.getElementById("chkAddCommentsOnAnalyze");
    if (cb) {
      cb.checked = isAddCommentsOnAnalyzeEnabled();
      cb.addEventListener("change", () => setAddCommentsOnAnalyze(!!cb.checked));
    } else {
      isAddCommentsOnAnalyzeEnabled();
    }
    const annotateBtn = document.getElementById("btnAnnotate");
    if (annotateBtn) {
      annotateBtn.addEventListener("click", async () => {
        var _a3, _b;
        if (annotateBtn.disabled) return;
        annotateBtn.disabled = true;
        try {
          const data = ((_b = (_a3 = window.__last) == null ? void 0 : _a3.analyze) == null ? void 0 : _b.json) || {};
          const findings = globalThis.parseFindings(data);
          await globalThis.annotateFindingsIntoWord(findings);
        } finally {
          annotateBtn.disabled = false;
        }
      });
      annotateBtn.classList.remove("js-disable-while-busy");
      annotateBtn.removeAttribute("disabled");
    }
    onDraftReady("");
    wireResultsToggle();
    console.log("Panel UI wired");
    const ab = document.getElementById("btnAnalyze");
    if (ab) ab.disabled = true;
    ensureHeaders();
    updateStatusChip();
  }
  g.wireUI = g.wireUI || wireUI;
  function onDraftReady(text) {
    const show = !!text.trim();
    const apply = document.getElementById("btnApplyTracked");
    const accept = document.getElementById("btnAcceptAll");
    const reject = document.getElementById("btnRejectAll");
    const diff = document.getElementById("btnPreviewDiff");
    const pane = document.getElementById("draftPane");
    const dst = document.getElementById("draftText");
    if (dst) dst.value = text;
    if (pane) pane.style.display = show ? "" : "none";
    if (apply) apply.disabled = !show;
    if (accept) accept.disabled = !show;
    if (reject) reject.disabled = !show;
    if (diff) diff.disabled = !show;
  }
  async function bootstrap(info) {
    var _a2;
    wireUI();
    try {
      await doHealth();
    } catch {
    }
    try {
      setOfficeBadge(`${(info == null ? void 0 : info.host) || ((_a2 = Office.context) == null ? void 0 : _a2.host) || "Word"} \u2713`);
    } catch {
      setOfficeBadge(null);
    }
  }
  if (!globalThis.__CAI_TESTING__) {
    document.addEventListener("DOMContentLoaded", () => {
      Violins.initAudio();
      Office.onReady((info) => bootstrap(info));
    });
  }
})();
