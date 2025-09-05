import { metaFromResponse, applyMetaToBadges, apiHealth, apiAnalyze, apiQaRecheck } from "./api-client";
import { notifyOk, notifyErr, notifyWarn } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

function $(sel: string): HTMLTextAreaElement | null {
  return document.querySelector(sel) as HTMLTextAreaElement | null;
}

function getSelectionAsync(): Promise<string> {
  return new Promise((resolve, reject) => {
    try {
      Office.context.document.getSelectedDataAsync(Office.CoercionType.Text, r => {
        if (r.status === Office.AsyncResultStatus.Succeeded) {
          resolve((r.value || "").toString().trim());
        } else {
          reject(r.error);
        }
      });
    } catch (e) { reject(e); }
  });
}

async function getSelectionContext(chars = 200): Promise<{ before: string; after: string; }> {
  try {
    return await Word.run(async ctx => {
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
    const el = document.getElementById("originalClause") as HTMLTextAreaElement | null;
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
    const el = document.getElementById("originalClause") as HTMLTextAreaElement | null;
    if (el) {
      el.value = txt;
      el.setAttribute("data-role", "source-loaded");
    }
  } catch (e) {
    notifyWarn("Failed to load document");
    console.error(e);
  }
}

async function onGetAIDraft(ev?: Event) {
  try {
    const src = $(Q.original);
    const dst = $(Q.proposed);

    const text = (src?.value ?? "").trim();
    if (!text) { notifyWarn("No source text"); return; }

    const modeSel = document.getElementById("cai-mode") as HTMLSelectElement | null;
    const mode = modeSel?.value || "friendly";
    const ctx = await getSelectionContext(200);

    const body = {
      text: "Please draft a neutral confidentiality clause.",
      mode,
      before_text: ctx.before,
      after_text: ctx.after,
    };

    const resp = await fetch(`${(window as any).__cal_base__ ?? ""}/api/gpt-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    try { applyMetaToBadges(metaFromResponse(resp)); } catch {}

    if (!resp.ok) {
      notifyWarn(`Draft failed (cid ${resp.headers.get('x-cid') || 'n/a'})`);
      return;
    }

    const json = await resp.json();
    const proposed = (json?.proposed_text ?? "").toString();

    if (dst) {
      if (!dst.id) dst.id = "proposedText";
      if (!dst.name) dst.name = "proposed";
      (dst as any).dataset.role = "proposed-text";
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
  try { applyMetaToBadges(meta); } catch {}
  notifyOk(`Health: ${json.status} (schema ${json.schema})`);
}

async function doAnalyzeDoc() {
  const text = await getWholeDocText();
  if (!text || !text.trim()) { notifyErr("В документе нет текста"); return; }
  const { json, meta } = await apiAnalyze(text);
  try { applyMetaToBadges(meta); } catch {}
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}

async function doQARecheck() {
  const text = await getWholeDocText();
  const { json, meta } = await apiQaRecheck(text, []);
  try { applyMetaToBadges(meta); } catch {}
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
  notifyOk("QA recheck OK");
}

function bindClick(sel: string, fn: () => void) {
  const el = document.querySelector(sel) as HTMLButtonElement | null;
  if (!el) return;
  el.addEventListener("click", (e) => { e.preventDefault(); fn(); });
  el.classList.remove("js-disable-while-busy");
  el.removeAttribute("disabled");
}

async function onApplyTracked() {
  try {
    const dst = $(Q.proposed);
    const proposed = (dst?.value || "").trim();
    if (!proposed) { notifyWarn("No draft to insert"); return; }
    await Word.run(async ctx => {
      let range = ctx.document.getSelection();
      (ctx.document as any).trackRevisions = true;
      range.insertText(proposed, "Replace");
      try { range.insertComment("AI draft"); } catch {}
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
  // 1) Ждём Office, если он есть. Если нет — ждём DOM.
  try {
    if ((window as any).Office?.onReady) {
      await (window as any).Office.onReady();
    } else {
      if (document.readyState === "loading") {
        await new Promise<void>(res => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
      }
    }
  } catch {}
  // 2) Немедленно провязываем UI
  wireUI();
  // 3) Пытаемся сразу применить мету хотя бы по /health
  try { await doHealth(); } catch {}
}

bootstrap();
