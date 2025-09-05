import { apiHealth, apiAnalyze, apiQaRecheck, apiGptDraft, metaFromResponse, applyMetaToBadges, parseFindings, AnalyzeFinding } from "./api-client";
import { notifyOk, notifyErr, notifyWarn } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

function slot(id: string, role: string): HTMLElement | null {
  return (
    document.querySelector(`[data-role="${role}"]`) as HTMLElement | null
  ) || document.getElementById(id);
}

export function normalizeText(s: string): string {
  return s.replace(/\r\n?/g, "\n").trim().replace(/[ \t]+/g, " ");
}

export function buildParagraphIndex(paragraphs: string[]): { starts: number[]; texts: string[] } {
  const starts: number[] = [];
  const texts: string[] = [];
  let pos = 0;
  for (const p of paragraphs) {
    const t = normalizeText(p);
    starts.push(pos);
    texts.push(t);
    pos += t.length + 1; // assume joined by \n
  }
  return { starts, texts };
}

export async function mapFindingToRange(f: AnalyzeFinding, index: { starts: number[]; texts: string[] }): Promise<Word.Range | null> {
  try {
    return await Word.run(async ctx => {
      const body = ctx.document.body;
      const searchRes = body.search(normalizeText(f.snippet), { matchCase: false, matchWholeWord: false });
      searchRes.load("items");
      await ctx.sync();
      return searchRes.items.length ? searchRes.items[0] : null;
    });
  } catch (e) {
    console.warn("mapFindingToRange fail", e);
    return null;
  }
}

export async function annotateFindingsIntoWord(findings: AnalyzeFinding[]) {
  for (const f of findings) {
    try {
      await Word.run(async ctx => {
        const body = ctx.document.body;
        const searchRes = body.search(normalizeText(f.snippet), { matchCase: false, matchWholeWord: false });
        searchRes.load("items");
        await ctx.sync();
        const range = searchRes.items[0];
        if (range) {
          const msg = `${f.rule_id} (${f.severity})${f.advice ? ": " + f.advice : ""}`;
          range.insertComment(msg);
        }
        await ctx.sync();
      });
    } catch (e) {
      console.warn("annotate fail", e);
    }
  }
}

export async function applyOpsTracked(ops: { start: number; end: number; replacement: string }[]) {
  if (!ops || !ops.length) return;
  const last: string = (window as any).__lastAnalyzed || "";
  await Word.run(async ctx => {
    const body = ctx.document.body;
    (ctx.document as any).trackRevisions = true;
    for (const op of ops) {
      const snippet = last.slice(op.start, op.end);
      const ranges = body.search(snippet, { matchCase: false, matchWholeWord: false });
      ranges.load("items");
      await ctx.sync();
      const range = ranges.items[0];
      if (range) {
        range.insertText(op.replacement, "Replace");
        try { range.insertComment("AI edit"); } catch {}
      }
      await ctx.sync();
    }
  });
}

async function acceptAll() {
  try {
    await Word.run(async ctx => {
      ctx.document.body.acceptAllChanges();
      await ctx.sync();
    });
    notifyOk("Accepted all changes");
  } catch (e) {
    notifyWarn("Accept failed");
    console.error(e);
  }
}

async function rejectAll() {
  try {
    await Word.run(async ctx => {
      ctx.document.body.rejectAllChanges();
      await ctx.sync();
    });
    notifyOk("Rejected all changes");
  } catch (e) {
    notifyWarn("Reject failed");
    console.error(e);
  }
}

async function navComments(dir: number) {
  try {
    await Word.run(async ctx => {
      const comments = ctx.document.body.getComments();
      comments.load("items");
      await ctx.sync();
      const list = comments.items;
      if (!list.length) return;
      const w: any = window as any;
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

function onPrevIssue() { navComments(-1); }
function onNextIssue() { navComments(1); }

function renderResults(res: any) {
  const clause = slot("resClauseType", "clause-type");
  if (clause) clause.textContent = res?.clause_type || "—";

  const findingsArr: AnalyzeFinding[] = parseFindings(res);
  const findingsList = slot("findingsList", "findings") as HTMLElement | null;
  if (findingsList) {
    findingsList.innerHTML = "";
    findingsArr.forEach((f: any) => {
      const li = document.createElement("li");
      li.textContent = typeof f === "string" ? f : JSON.stringify(f);
      findingsList.appendChild(li);
    });
  }

  const recoArr = Array.isArray(res?.recommendations) ? res.recommendations : [];
  const recoList = slot("recoList", "recommendations") as HTMLElement | null;
  if (recoList) {
    recoList.innerHTML = "";
    recoArr.forEach((r: any) => {
      const li = document.createElement("li");
      li.textContent = typeof r === "string" ? r : JSON.stringify(r);
      recoList.appendChild(li);
    });
  }

  const count = slot("resFindingsCount", "findings-count");
  if (count) count.textContent = String(findingsArr.length);

  const pre = slot("rawJson", "raw-json") as HTMLElement | null;
  if (pre) pre.textContent = JSON.stringify(res ?? {}, null, 2);
}

function wireResultsToggle() {
  const toggle = slot("toggleRaw", "toggle-raw-json");
  const pre = slot("rawJson", "raw-json") as HTMLElement | null;
  if (toggle && pre) {
    pre.style.display = "none";
    toggle.addEventListener("click", () => {
      pre.style.display = pre.style.display === "none" ? "block" : "none";
    });
  }
}

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


async function onGetAIDraft(ev?: Event) {
  try {
    const src = $(Q.original);
    const dst = $(Q.proposed);

    let text = (src?.value ?? "").trim();
    if (!text) {
      try {
        text = await getSelectionAsync();
        if (src) src.value = text;
      } catch {}
    }
    if (!text) { notifyWarn("No source text"); return; }

    const modeSel = document.getElementById("cai-mode") as HTMLSelectElement | null;
    const mode = modeSel?.value || "friendly";
    const ctx = await getSelectionContext(200);
    const { ok, json, resp } = await apiGptDraft(
      text,
      mode,
      { before_text: ctx.before, after_text: ctx.after }
    );
    if (!ok) { notifyWarn("Draft failed"); return; }
    try { applyMetaToBadges(metaFromResponse(resp)); } catch {}
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
    const { ok, json, resp } = await apiHealth();
    try { applyMetaToBadges(metaFromResponse(resp)); } catch {}
    setConnBadge(ok);
    notifyOk(`Health: ${json.status} (schema ${json.schema})`);
  } catch (e) {
    setConnBadge(false);
    notifyWarn("Health failed");
    console.error(e);
  }
}

async function doAnalyze() {
  const useSel = (document.getElementById("chkUseSelection") as HTMLInputElement | null)?.checked;
  const raw = useSel ? await getSelectionAsync().catch(() => "") : await getWholeDocText();
  const text = normalizeText(raw || "");
  if (!text) { notifyErr("В документе нет текста"); return; }
  (window as any).__lastAnalyzed = text;
  const { json, resp } = await apiAnalyze(text);
  try { applyMetaToBadges(metaFromResponse(resp)); } catch {}
  renderResults(json);
  (document.getElementById("btnAnnotate") as HTMLButtonElement | null)?.removeAttribute("disabled");
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}

async function doQARecheck() {
  const text = await getWholeDocText();
  const { json, resp } = await apiQaRecheck(text, []);
  try { applyMetaToBadges(metaFromResponse(resp)); } catch {}
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
    const last = (window as any).__last || {};
    const ops = last["gpt-draft"]?.json?.ops || last["suggest"]?.json?.ops || [];
    if (!ops.length) { notifyWarn("No ops to apply"); return; }
    await applyOpsTracked(ops);
    notifyOk("Applied ops");
  } catch (e) {
    notifyWarn("Insert failed");
    console.error(e);
  }
}

function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyze", doAnalyze);
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
  bindClick("#btnInsertIntoWord", onInsertIntoWord);
  bindClick("#btnApplyTracked", onApplyTracked);
  bindClick("#btnAcceptAll", acceptAll);
  bindClick("#btnRejectAll", rejectAll);
  bindClick("#btnPrevIssue", onPrevIssue);
  bindClick("#btnNextIssue", onNextIssue);
  bindClick("#btnAnnotate", () => {
    const data = (window as any).__last?.analyze?.json || {};
    const findings = parseFindings(data);
    annotateFindingsIntoWord(findings);
  });
  wireResultsToggle();
  console.log("Panel UI wired");
}

async function onInsertIntoWord() {
  try {
    const dst = $(Q.proposed);
    const txt = (dst?.value || "").trim();
    if (!txt) { notifyWarn("No draft to insert"); return; }
    if ((window as any).Office && (window as any).Word) {
      await Word.run(async ctx => {
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
    try { await navigator.clipboard.writeText($(Q.proposed)?.value || ""); } catch {}
    notifyWarn("Not in Office environment; result copied to clipboard");
    console.error(e);
  }
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
