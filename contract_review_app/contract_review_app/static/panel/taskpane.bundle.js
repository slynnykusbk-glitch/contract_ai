(() => {
  // word_addin_dev/app/assets/api-client.ts
  function parseFindings(resp) {
    const arr = resp?.analysis?.findings ?? resp?.findings ?? resp?.issues ?? [];
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

  // word_addin_dev/app/assets/store.ts
  var DEFAULT_API_KEY = "";
  var DEFAULT_SCHEMA = "1.4";
  function ensureDefaults() {
    try {
      if (localStorage.getItem("api_key") === null) {
        localStorage.setItem("api_key", DEFAULT_API_KEY);
      }
      if (localStorage.getItem("schema_version") === null) {
        localStorage.setItem("schema_version", DEFAULT_SCHEMA);
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
  var root = typeof globalThis !== "undefined" ? globalThis : window;
  root.CAI = root.CAI || {};
  root.CAI.Store = root.CAI.Store || {};
  root.CAI.Store.setApiKey = setApiKey;
  root.CAI.Store.setSchemaVersion = setSchemaVersion;
  root.CAI.Store.get = () => ({ apiKey: getApiKeyFromStore(), schemaVersion: getSchemaFromStore() });
  root.CAI.Store.DEFAULT_BASE = root.CAI.Store.DEFAULT_BASE || "https://localhost:9443";

  // contract_review_app/frontend/common/http.ts
  var LS = { API_KEY: "api_key", SCHEMA: "schema_version" };
  function getStoredKey() {
    return localStorage.getItem(LS.API_KEY) ?? "";
  }
  function getStoredSchema() {
    return localStorage.getItem(LS.SCHEMA) ?? "";
  }
  function setStoredSchema(v) {
    if (v) localStorage.setItem(LS.SCHEMA, v);
  }
  function ensureHeadersSet() {
    try {
      if (!localStorage.getItem(LS.API_KEY)) {
        localStorage.setItem(LS.API_KEY, "local-test-key-123");
      }
      if (!localStorage.getItem(LS.SCHEMA)) {
        localStorage.setItem(LS.SCHEMA, "1.4");
      }
    } catch {
    }
  }
  async function postJSON(url, body, extra = {}) {
    const headers = {
      "Content-Type": "application/json",
      "x-api-key": getStoredKey(),
      "x-schema-version": getStoredSchema(),
      ...extra
    };
    const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
    const respSchema = r.headers.get("x-schema-version");
    if (respSchema) setStoredSchema(respSchema);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    if (data?.schema) setStoredSchema(data.schema);
    return data;
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
  var g = globalThis;
  g.parseFindings = g.parseFindings || parseFindings;
  g.applyMetaToBadges = g.applyMetaToBadges || applyMetaToBadges;
  g.getApiKeyFromStore = g.getApiKeyFromStore || getApiKeyFromStore;
  g.getSchemaFromStore = g.getSchemaFromStore || getSchemaFromStore;
  g.getWholeDocText = g.getWholeDocText || getWholeDocText;
  var Q = {
    proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
    original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
  };
  var lastCid = "";
  function getBackend() {
    try {
      return (localStorage.getItem("backendUrl") || "https://localhost:9443").replace(/\/+$/, "");
    } catch {
      return "https://localhost:9443";
    }
  }
  function ensureHeaders() {
    ensureHeadersSet();
    try {
      const store = globalThis.CAI?.Store?.get?.() || {};
      const apiKey = store.apiKey || getApiKeyFromStore();
      const schema = store.schemaVersion || getSchemaFromStore();
      if (apiKey) {
        try {
          localStorage.setItem("api_key", apiKey);
        } catch {
        }
      }
      if (schema) {
        try {
          setStoredSchema(schema);
        } catch {
        }
      }
    } catch {
    }
    return true;
  }
  function slot(id, role) {
    return document.querySelector(`[data-role="${role}"]`) || document.getElementById(id);
  }
  function normalizeText(s) {
    if (!s) return "";
    return s.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/[ \t]+/g, " ").trim();
  }
  function getRiskThreshold() {
    const sel = document.getElementById("selectRiskThreshold") || document.getElementById("riskThreshold");
    const v = sel?.value?.toLowerCase();
    return v === "low" || v === "medium" || v === "high" ? v : "medium";
  }
  function isAddCommentsOnAnalyzeEnabled() {
    const cb = document.getElementById("cai-comment-on-analyze") || document.getElementById("chkAddCommentsOnAnalyze");
    return cb ? !!cb.checked : true;
  }
  function severityRank(s) {
    const m = (s || "").toLowerCase();
    return m === "high" ? 3 : m === "medium" ? 2 : 1;
  }
  function filterByThreshold(list, thr) {
    const min = severityRank(thr);
    return (list || []).filter((f) => severityRank(f.severity) >= min);
  }
  function buildLegalComment(f) {
    const sev = (f.severity || "info").toUpperCase();
    const rid = f.rule_id || "rule";
    const ct = f.clause_type ? ` (${f.clause_type})` : "";
    const advice = f.advice || "\u2014";
    const law = Array.isArray(f.law_refs) && f.law_refs.length ? f.law_refs.join("; ") : "\u2014";
    const conflict = Array.isArray(f.conflict_with) && f.conflict_with.length ? f.conflict_with.join("; ") : "\u2014";
    const fix = f.suggestion?.text || "\u2014";
    return `[${sev}] ${rid}${ct}
Reason: ${advice}
Law: ${law}
Conflict: ${conflict}
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
      console.warn("mapFindingToRange fail", e);
      return null;
    }
  }
  async function annotateFindingsIntoWord(findings) {
    const base2 = normalizeText(window.__lastAnalyzed || "");
    const list = (findings || []).map((f) => ({
      ...f,
      snippet: normalizeText(f.snippet || ""),
      start: typeof f.start === "number" ? f.start : 0,
      end: typeof f.end === "number" ? f.end : typeof f.start === "number" ? f.start + normalizeText(f.snippet || "").length : normalizeText(f.snippet || "").length
    }));
    list.sort((a, b) => (b.end ?? 0) - (a.end ?? 0));
    let lastStart = Number.POSITIVE_INFINITY;
    let skipped = 0;
    for (const f of list) {
      const snippet = f.snippet;
      if (!snippet) continue;
      const end = typeof f.end === "number" ? f.end : f.start + snippet.length;
      if (end > lastStart) {
        skipped++;
        continue;
      }
      const occIdx = (() => {
        if (typeof f.start !== "number" || !snippet) return 0;
        let idx = -1, n = 0;
        while ((idx = base2.indexOf(snippet, idx + 1)) !== -1 && idx < f.start) n++;
        return n;
      })();
      const tryInsert = async () => {
        await Word.run(async (ctx) => {
          const body = ctx.document.body;
          const s1 = body.search(snippet, { matchCase: false, matchWholeWord: false });
          s1.load("items");
          await ctx.sync();
          let target = s1.items?.[Math.min(occIdx, Math.max(0, (s1.items || []).length - 1))];
          if (!target) {
            const token = (() => {
              const tokens = snippet.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter((x) => x.length >= 12);
              if (tokens.length) return tokens.sort((a, b) => b.length - a.length)[0].slice(0, 64);
              const i = Math.max(0, f.start ?? 0);
              return base2.slice(i, i + 40);
            })();
            if (token && token.trim()) {
              const s2 = body.search(token, { matchCase: false, matchWholeWord: false });
              s2.load("items");
              await ctx.sync();
              target = s2.items?.[Math.min(occIdx, Math.max(0, (s2.items || []).length - 1))];
            }
          }
          if (target) {
            const msg = buildLegalComment(f);
            target.insertComment(msg);
          } else {
            console.warn("[annotate] no match for snippet/anchor", { rid: f.rule_id, snippet: snippet.slice(0, 120) });
          }
          await ctx.sync();
        });
      };
      try {
        await tryInsert();
      } catch (e) {
        if (String(e).includes("0xA7210002")) {
          try {
            await tryInsert();
          } catch (e2) {
            console.warn("annotate retry failed", e2);
          }
        } else {
          console.warn("annotate error", e);
        }
      }
      lastStart = typeof f.start === "number" ? f.start : lastStart;
    }
    if (skipped) notifyWarn(`Skipped ${skipped} overlaps`);
  }
  g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;
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
      for (const op of cleaned) {
        const snippet = last.slice(op.start, op.end);
        const occIdx = (() => {
          let idx = -1, n = 0;
          while ((idx = last.indexOf(snippet, idx + 1)) !== -1 && idx < op.start) n++;
          return n;
        })();
        const found = body.search(snippet, { matchCase: false, matchWholeWord: false });
        found.load("items");
        await ctx.sync();
        const items = found.items || [];
        const target = items[Math.min(occIdx, Math.max(0, items.length - 1))];
        if (target) {
          target.insertText(op.replacement, "Replace");
          try {
            target.insertComment("AI edit");
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
  async function navComments(dir) {
    try {
      await Word.run(async (ctx) => {
        const comments = ctx.document.body.getComments();
        comments.load("items");
        await ctx.sync();
        const list = comments.items;
        if (!list.length) return;
        const w = window;
        w.__caiNavIdx = (w.__caiNavIdx ?? -1) + dir;
        if (w.__caiNavIdx < 0) w.__caiNavIdx = list.length - 1;
        if (w.__caiNavIdx >= list.length) w.__caiNavIdx = 0;
        list[w.__caiNavIdx].getRange().select();
        await ctx.sync();
      });
    } catch (e) {
      console.warn("nav comment fail", e);
    }
  }
  function onPrevIssue() {
    navComments(-1);
  }
  function onNextIssue() {
    navComments(1);
  }
  function renderResults(res) {
    const clause = slot("resClauseType", "clause-type");
    if (clause) clause.textContent = res?.clause_type || "\u2014";
    const findingsArr = parseFindings(res);
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
  async function onUseWholeDoc() {
    const src = $(Q.original);
    const raw = await getWholeDocText();
    const text = normalizeText(raw || "");
    if (src) {
      src.value = text;
      src.dispatchEvent(new Event("input", { bubbles: true }));
    }
    window.__lastAnalyzed = text;
    window.toast?.("Whole doc loaded");
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
      if (!lastCid) {
        notifyWarn("Analyze first");
        return;
      }
      const json = await postJSON(`${getBackend()}/api/gpt-draft`, { cid: lastCid, clause: text, mode });
      const proposed = (json?.proposed_text ?? json?.draft_text ?? "").toString();
      if (dst) {
        if (!dst.id) dst.id = "proposedText";
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
      const prev = getStoredSchema();
      const resp = await fetch(`${getBackend()}/health`, { method: "GET" });
      const json = await resp.json().catch(() => ({}));
      const schema = resp.headers.get("x-schema-version") || json?.schema || null;
      if (schema) {
        setStoredSchema(schema);
        if (schema !== prev) {
          console.log(`schema: ${schema} (synced)`);
        }
      }
      setConnBadge(true);
      try {
        applyMetaToBadges({
          cid: null,
          xcache: null,
          latencyMs: null,
          schema: schema || null,
          provider: json?.provider || null,
          model: json?.model || null,
          llm_mode: null,
          usage: null,
          status: json?.status || null
        });
      } catch {
      }
      notifyOk(`Health: ${json?.status || "ok"}${schema ? ` (schema ${schema})` : ""}`);
    } catch (e) {
      setConnBadge(false);
      notifyWarn("Health failed");
      console.error(e);
    }
  }
  async function doAnalyze() {
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
      const headers = {
        "Content-Type": "application/json",
        "x-api-key": getStoredKey(),
        "x-schema-version": getStoredSchema()
      };
      const resp = await fetch(`${getBackend()}/api/analyze`, {
        method: "POST",
        headers,
        body: JSON.stringify({ text: base2 })
      });
      const respSchema = resp.headers.get("x-schema-version");
      if (respSchema) setStoredSchema(respSchema);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      if (json?.schema) setStoredSchema(json.schema);
      lastCid = resp.headers.get("x-cid") || "";
      renderResults(json);
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
    }
  }
  async function doQARecheck() {
    ensureHeaders();
    const text = await getWholeDocText();
    const json = await postJSON(`${getBackend()}/api/qa-recheck`, { text, rules: {} });
    (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
    const ok = !json?.error;
    if (ok) {
      notifyOk("QA recheck OK");
    } else {
      const msg = json?.error || json?.message || "unknown";
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
  async function onApplyTracked() {
    try {
      const last = window.__last || {};
      const ops = last["gpt-draft"]?.json?.ops || last["suggest"]?.json?.ops || [];
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
      window.toast?.("Rejected");
      console.log("[OK] Rejected");
    } catch (e) {
      window.toast?.("Reject failed");
      console.error(e);
    }
  }
  function wireUI() {
    bindClick("#btnUseWholeDoc", onUseWholeDoc);
    bindClick("#btnAnalyze", doAnalyze);
    bindClick("#btnTest", doHealth);
    bindClick("#btnQARecheck", doQARecheck);
    document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
    bindClick("#btnInsertIntoWord", onInsertIntoWord);
    bindClick("#btnApplyTracked", onApplyTracked);
    bindClick("#btnAcceptAll", onAcceptAll);
    bindClick("#btnRejectAll", onRejectAll);
    bindClick("#btnPrevIssue", onPrevIssue);
    bindClick("#btnNextIssue", onNextIssue);
    bindClick("#btnAnnotate", () => {
      const data = window.__last?.analyze?.json || {};
      const findings = globalThis.parseFindings(data);
      globalThis.annotateFindingsIntoWord(findings);
    });
    onDraftReady("");
    wireResultsToggle();
    console.log("Panel UI wired");
    ensureHeaders();
  }
  g.wireUI = g.wireUI || wireUI;
  function onDraftReady(text) {
    const btn = document.getElementById("btnInsertIntoWord");
    const show = !!text.trim();
    btn.style.display = show ? "inline-block" : "none";
    btn.disabled = !show;
  }
  async function onInsertIntoWord() {
    const dst = $(Q.proposed);
    const txt = (dst?.value || "").trim();
    if (!txt) {
      notifyWarn("No draft to insert");
      return;
    }
    try {
      await insertIntoWord(txt);
      notifyOk("Inserted into Word");
    } catch (e) {
      console.error(e);
      await navigator.clipboard?.writeText(txt).catch(() => {
      });
      notifyWarn("Insert failed; draft copied to clipboard");
    }
  }
  async function insertIntoWord(text) {
    const w = window;
    if (w?.Office?.context?.document?.setSelectedDataAsync) {
      await new Promise(
        (resolve, reject) => w.Office.context.document.setSelectedDataAsync(
          text,
          { coercionType: w.Office.CoercionType.Text },
          (res) => res?.status === w.Office.AsyncResultStatus.Succeeded ? resolve() : reject(res?.error)
        )
      );
    } else {
      await navigator.clipboard?.writeText(text).catch(() => {
      });
      alert("Draft copied to clipboard (Office not ready). Paste it into the document.");
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
  bootstrap();
})();
