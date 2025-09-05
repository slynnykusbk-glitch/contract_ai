import { apiHealth, apiAnalyze, apiQaRecheck, apiGptDraft } from "./api-client";
import { notifyOk, notifyErr, notifyWarn } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

function setConnBadge(ok: boolean | null) {
  const el = document.getElementById("connBadge");
  if (el) el.textContent = `Conn: ${ok === null ? "—" : ok ? "✓" : "×"}`;
}

function setOfficeBadge(txt: string | null) {
  const el = document.getElementById("officeBadge");
  if (el) el.textContent = `Office: ${txt ?? "—"}`;
}

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
    const { ok, json } = await apiGptDraft(
      "Please draft a neutral confidentiality clause.",
      mode,
      { before_text: ctx.before, after_text: ctx.after }
    );
    if (!ok) { notifyWarn("Draft failed"); return; }
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
  try {
    const { ok, json } = await apiHealth();
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
  if (!text || !text.trim()) { notifyErr("В документе нет текста"); return; }
  const { json } = await apiAnalyze(text);
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}

async function doQARecheck() {
  const text = await getWholeDocText();
  const { json } = await apiQaRecheck(text, []);
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
  if (document.readyState === "loading") {
    await new Promise<void>(res => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
  }
  wireUI();
  try { await doHealth(); } catch {}
  try {
    if ((window as any).Office?.onReady) {
      const info = await (window as any).Office.onReady();
      setOfficeBadge(`${info?.host || "Word"} ✓`);
    }
  } catch {
    setOfficeBadge(null);
  }
}

bootstrap();
