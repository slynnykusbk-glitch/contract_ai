// word_addin_dev/app/assets/api-client.js
function metaFromResponse(resp) {
  const h = resp.headers;
  const get = (n) => h.get(n) || null;
  return {
    cid: get("x-cid"),
    xcache: get("x-cache"),
    latencyMs: Number(get("x-latency-ms")) || null,
    schema: get("x-schema-version"),
    provider: get("x-provider"),
    model: get("x-model"),
    llm_mode: get("x-llm-mode"),
    usage: get("x-usage-total")
  };
}
function applyMetaToBadges(m) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v ?? "\u2014";
  };
  set("cid", m.cid);
  set("xcache", m.xcache);
  set("latency", m.latencyMs == null ? "\u2014" : String(m.latencyMs));
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
async function req(path, { method = "GET", body = null } = {}) {
  const r = await fetch(base() + path, {
    method,
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : void 0,
    credentials: "include"
  });
  const json = await r.json().catch(() => ({}));
  return { ok: r.ok, json, resp: r };
}
async function apiHealth() {
  const { ok, json, resp } = await req("/health");
  return { ok, json, meta: metaFromResponse(resp) };
}
async function apiAnalyze(text) {
  const { ok, json, resp } = await req("/api/analyze", { method: "POST", body: { text, mode: "live" } });
  return { ok, json, meta: metaFromResponse(resp) };
}
async function apiQaRecheck(text, rules = []) {
  const { ok, json, resp } = await req("/api/qa-recheck", { method: "POST", body: { text, rules } });
  return { ok, json, meta: metaFromResponse(resp) };
}

// word_addin_dev/app/assets/notifier.js
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

// word_addin_dev/app/assets/office.js
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
    const text = (src?.value ?? "").trim();
    if (!text) {
      notifyWarn("No source text");
      return;
    }
    const modeSel = document.getElementById("cai-mode");
    const mode = modeSel?.value || "friendly";
    const ctx = await getSelectionContext(200);
    const body = {
      text: "Please draft a neutral confidentiality clause.",
      mode,
      before_text: ctx.before,
      after_text: ctx.after
    };
    const resp = await fetch(`${window.__cal_base__ ?? ""}/api/gpt-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    try {
      applyMetaToBadges(metaFromResponse(resp));
    } catch {
    }
    if (!resp.ok) {
      notifyWarn(`Draft failed (cid ${resp.headers.get("x-cid") || "n/a"})`);
      return;
    }
    const json = await resp.json();
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
  const { json, meta } = await apiHealth();
  try {
    applyMetaToBadges(meta);
  } catch {
  }
  notifyOk(`Health: ${json.status} (schema ${json.schema})`);
}
async function doAnalyzeDoc() {
  const text = await getWholeDocText();
  if (!text || !text.trim()) {
    notifyErr("\u0412 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435 \u043D\u0435\u0442 \u0442\u0435\u043A\u0441\u0442\u0430");
    return;
  }
  const { json, meta } = await apiAnalyze(text);
  try {
    applyMetaToBadges(meta);
  } catch {
  }
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}
async function doQARecheck() {
  const text = await getWholeDocText();
  const { json, meta } = await apiQaRecheck(text, []);
  try {
    applyMetaToBadges(meta);
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
function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyzeDoc", doAnalyzeDoc);
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
  bindClick("#btn-use-selection", onUseSelection);
  bindClick("#btn-use-whole", onUseWholeDoc);
  bindClick("#btnApplyTracked", onApplyTracked);
  bindClick("#btnAcceptAll", () => notifyWarn("Not implemented"));
  bindClick("#btnRejectAll", () => notifyWarn("Not implemented"));
  console.log("Panel UI wired");
}
async function bootstrap() {
  try {
    if (window.Office?.onReady) {
      await window.Office.onReady();
    } else {
      if (document.readyState === "loading") {
        await new Promise((res) => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
      }
    }
  } catch {
  }
  wireUI();
  try {
    await doHealth();
  } catch {
  }
}
bootstrap();
