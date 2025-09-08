(() => {
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
  async function apiQaRecheck(text, rules = {}) {
    const dict = Array.isArray(rules) ? Object.assign({}, ...rules) : (rules || {});
    return req("/api/qa-recheck", { method: "POST", body: { text, rules: dict }, key: "qa-recheck" });
  }
  async function postRedlines(before_text, after_text) {
    return req("/api/panel/redlines", { method: "POST", body: { before_text, after_text }, key: "redlines" });
  }

  // app/assets/notifier.ts
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

  // app/assets/office.ts
  async function getWholeDocText() {
    return await Word.run(async (ctx) => {
      const body = ctx.document.body;
      body.load("text");
      await ctx.sync();
      return (body.text || "").trim();
    });
  }

  async function getSelectedText() {
    return await Word.run(async (ctx) => {
      const sel = ctx.document.getSelection();
      sel.load("text");
      await ctx.sync();
      return (sel.text || "").trim();
    });
  }

  // app/assets/taskpane.ts
  var g = globalThis;
  g.parseFindings = g.parseFindings || parseFindings;
  g.apiAnalyze = g.apiAnalyze || apiAnalyze;
  g.applyMetaToBadges = g.applyMetaToBadges || applyMetaToBadges;
  g.metaFromResponse = g.metaFromResponse || metaFromResponse;
  g.getWholeDocText = g.getWholeDocText || getWholeDocText;
  g.getSelectedText = g.getSelectedText || getSelectedText;
  g.postRedlines = g.postRedlines || postRedlines;
  var Q = {
    proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
    original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
  };
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
    const law = Array.isArray(f.law_refs) && f.law_refs.length ? f.law_refs.join('; ') : "\u2014";
    const conflict = Array.isArray(f.conflict_with) && f.conflict_with.length ? f.conflict_with.join('; ') : "\u2014";
    const fix = f.suggestion && f.suggestion.text ? f.suggestion.text : "\u2014";
    return `[${sev}] ${rid}${ct}\nReason: ${advice}\nLaw: ${law}\nConflict: ${conflict}\nSuggested fix: ${fix}`;
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
    for (const f of findings) {
      const snippet = normalizeText(f.snippet || "");
      if (!snippet) continue;
      const occIdx = (() => {
        if (typeof f.start !== "number" || !snippet) return 0;
        let idx = -1, n = 0;
        while ((idx = base2.indexOf(snippet, idx + 1)) !== -1 && idx < f.start) n++;
        return n;
      })();
      try {
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
      } catch (e) {
        console.warn("annotate error", e);
      }
    }
  }
  g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;
  async function applyOpsTracked(ops) {
    if (!ops || !ops.length) return;
    const last = window.__lastAnalyzed || "";
    await Word.run(async (ctx) => {
      const body = ctx.document.body;
      ctx.document.trackRevisions = true;
      for (const op of ops) {
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
  async function doAnalyze() {
    try {
      const cached = window.__lastAnalyzed;
      const base2 = cached && cached.trim() ? cached : normalizeText(await globalThis.getWholeDocText());
      if (!base2) {
        notifyErr("\u0412 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435 \u043D\u0435\u0442 \u0442\u0435\u043A\u0441\u0442\u0430");
        return;
      }
      window.__lastAnalyzed = base2;
      const { json, resp } = await globalThis.apiAnalyze(base2);
      try {
        globalThis.applyMetaToBadges(globalThis.metaFromResponse(resp));
      } catch {
      }
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
    const text = await getSelectedText();
    if (!text) {
      notifyWarn("Select clause text first");
      return;
    }
    const { json, resp } = await postJson("/api/qa-recheck", { text, rules: {} });
    try {
      applyMetaToBadges(metaFromResponse(resp));
    } catch {
    }
    (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
    notifyOk("QA recheck OK");
  }
  async function doRedlines() {
    const before = document.getElementById("originalClause")?.value || "";
    const after = document.getElementById("draftBox")?.value || "";
    const { json, resp } = await postRedlines(before, after);
    try {
      applyMetaToBadges(metaFromResponse(resp));
    } catch {
    }
    const container = document.getElementById("results") || document.body;
    if (json?.diff_html) container.innerHTML = json.diff_html;
    container.dispatchEvent(new CustomEvent("ca.redlines", { detail: json }));
    notifyOk("Redlines OK");
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
    bindClick("#btnRedlines", doRedlines);
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
    wireResultsToggle();
    console.log("Panel UI wired");
  }
  g.wireUI = g.wireUI || wireUI;
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
  bootstrap();
})();
