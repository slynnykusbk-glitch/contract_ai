import { applyMetaToBadges, parseFindings, AnalyzeFinding } from "./api-client";
import { normalizeText, dedupeFindings, severityRank } from "./dedupe";
export { normalizeText, dedupeFindings } from "./dedupe";
import { getApiKeyFromStore, getSchemaFromStore } from "./store";
import { postJSON, getStoredKey, getStoredSchema, setStoredSchema, ensureHeadersSet } from "../../../contract_review_app/frontend/common/http";
const g: any = globalThis as any;
g.parseFindings = g.parseFindings || parseFindings;
g.applyMetaToBadges = g.applyMetaToBadges || applyMetaToBadges;
g.getApiKeyFromStore = g.getApiKeyFromStore || getApiKeyFromStore;
g.getSchemaFromStore = g.getSchemaFromStore || getSchemaFromStore;
import { notifyOk, notifyErr, notifyWarn } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.
g.getWholeDocText = g.getWholeDocText || getWholeDocText;

type Mode = "live" | "friendly" | "doctor";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

let lastCid: string = "";

function getBackend(): string {
  try { return (localStorage.getItem('backendUrl') || 'https://localhost:9443').replace(/\/+$/, ''); }
  catch { return 'https://localhost:9443'; }
}

function ensureHeaders(): boolean {
  // Try to populate required headers from either CAI.Store or
  // localStorage but never block user actions if they are missing.
  ensureHeadersSet();
  try {
    const store = (globalThis as any).CAI?.Store?.get?.() || {};
    const apiKey = store.apiKey || getApiKeyFromStore();
    const schema = store.schemaVersion || getSchemaFromStore();
    if (apiKey) {
      try { localStorage.setItem('api_key', apiKey); } catch {}
    }
    if (schema) {
      try { setStoredSchema(schema); } catch {}
    }
  } catch {
    // swallow errors – missing storage should not stop the flow
  }
  return true; // allow all actions regardless of header state
}

function slot(id: string, role: string): HTMLElement | null {
  return (
    document.querySelector(`[data-role="${role}"]`) as HTMLElement | null
  ) || document.getElementById(id);
}

function getRiskThreshold(): "low" | "medium" | "high" {
  const sel = (document.getElementById("selectRiskThreshold") as HTMLSelectElement | null)
    || (document.getElementById("riskThreshold") as HTMLSelectElement | null);
  const v = sel?.value?.toLowerCase();
  return (v === "low" || v === "medium" || v === "high") ? v : "medium";
}

export function isAddCommentsOnAnalyzeEnabled(): boolean {
  try {
    const key = "cai-comment-on-analyze";
    const stored = localStorage.getItem(key);
    const def = stored === null ? (localStorage.setItem(key, "1"), true) : stored !== "0";
    const cb = (document.getElementById("cai-comment-on-analyze") as HTMLInputElement | null)
      || (document.getElementById("chkAddCommentsOnAnalyze") as HTMLInputElement | null);
    if (cb) cb.checked = def;
    return cb ? !!cb.checked : def;
  } catch {
    return true;
  }
}

export function setAddCommentsOnAnalyze(val: boolean): void {
  try { localStorage.setItem("cai-comment-on-analyze", val ? "1" : "0"); } catch {}
}

function isDryRunAnnotateEnabled(): boolean {
  const cb = document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null;
  return cb ? !!cb.checked : false;
}

function filterByThreshold(list: AnalyzeFinding[], thr: "low" | "medium" | "high"): AnalyzeFinding[] {
  const min = severityRank(thr);
  return (list || []).filter(f => severityRank(f.severity) >= min);
}

function buildLegalComment(f: AnalyzeFinding): string {
  const sev = (f.severity || "info").toUpperCase();
  const rid = f.rule_id || "rule";
  const ct = f.clause_type ? ` (${f.clause_type})` : "";
  const advice = f.advice || "—";
  const law = Array.isArray(f.law_refs) && f.law_refs.length ? f.law_refs.join('; ') : "—";
  const conflict = Array.isArray(f.conflict_with) && f.conflict_with.length ? f.conflict_with.join('; ') : "—";
  const fix = f.suggestion?.text || '—';
  return `[${sev}] ${rid}${ct}\nReason: ${advice}\nLaw: ${law}\nConflict: ${conflict}\nSuggested fix: ${fix}`;
}

function nthOccurrenceIndex(hay: string, needle: string, startPos?: number): number {
  if (!needle) return 0;
  let idx = -1, n = 0;
  const bound = typeof startPos === "number" ? Math.max(0, startPos) : Number.MAX_SAFE_INTEGER;
  while ((idx = hay.indexOf(needle, idx + 1)) !== -1 && idx < bound) n++;
  return n;
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

export async function mapFindingToRange(
  f: AnalyzeFinding,
): Promise<Word.Range | null> {
  const last: string = (window as any).__lastAnalyzed || "";
  const base = normalizeText(last);
  const snippet = normalizeText(f.snippet || "");
  const occIdx = nthOccurrenceIndex(base, snippet, f.start);

  try {
    return await Word.run(async ctx => {
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

export async function annotateFindingsIntoWord(findings: AnalyzeFinding[]) {
  const base = normalizeText((window as any).__lastAnalyzed || "");

  const deduped = dedupeFindings(findings || []);
  const list = deduped.slice().sort((a, b) => (b.end ?? 0) - (a.end ?? 0));

  let lastStart = Number.POSITIVE_INFINITY;
  let skipped = 0;

  for (const f of list) {
    const snippet = f.snippet;
    if (!snippet) continue;

    const end = typeof f.end === "number" ? f.end : (typeof f.start === "number" ? f.start + snippet.length : undefined);
    if (typeof end === "number" && end > lastStart) {
      skipped++;
      continue;
    }

    const occIdx = (() => {
      if (typeof f.start !== "number" || !snippet) return 0;
      let idx = -1, n = 0;
      while ((idx = base.indexOf(snippet, idx + 1)) !== -1 && idx < f.start) n++;
      return n;
    })();

    const tryInsert = async (mode: "normal" | "anchor" | "selection") => {
      await Word.run(async ctx => {
        const body = ctx.document.body;

        if (mode === "selection") {
          const sel = ctx.document.getSelection();
          const msgSel = `${buildLegalComment(f)} (fallback)`;
          if (!isDryRunAnnotateEnabled()) sel.insertComment(msgSel);
          await ctx.sync();
          return;
        }

        const s1 = body.search(snippet, { matchCase: false, matchWholeWord: false });
        s1.load("items");
        await ctx.sync();
        let target = s1.items?.[Math.min(occIdx, Math.max(0, (s1.items || []).length - 1))];

        if (!target) {
          const token = (() => {
            const tokens = snippet.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter(x => x.length >= 12);
            if (tokens.length) return tokens.sort((a, b) => b.length - a.length)[0].slice(0, 64);
            const i = Math.max(0, f.start ?? 0);
            return base.slice(i, i + 40);
          })();

          if (token && token.trim()) {
            const s2 = body.search(token, { matchCase: false, matchWholeWord: false });
            s2.load("items");
            await ctx.sync();
            target = s2.items?.[Math.min(occIdx, Math.max(0, (s2.items || []).length - 1))];
          }
        }

        if (target) {
          if (mode === "anchor") target = target.getRange("Start");
          if (isDryRunAnnotateEnabled()) {
            try { target.select(); } catch {}
          } else {
            const msg = buildLegalComment(f);
            target.insertComment(msg);
          }
        } else {
          console.warn("[annotate] no match for snippet/anchor", { rid: f.rule_id, snippet: snippet.slice(0, 120) });
        }
        await ctx.sync();
      });
    };

    try {
      await tryInsert("normal");
    } catch (e) {
      if (String(e).includes("0xA7210002")) {
        console.warn("panel:annotate", { rid: f.rule_id, fallback: "anchor" });
        try {
          await tryInsert("anchor");
        } catch (e2) {
          console.warn("panel:annotate", { rid: f.rule_id, fallback: "selection" });
          try {
            await tryInsert("selection");
          } catch (e3) {
            console.warn("annotate retry failed", e3);
          }
        }
      } else {
        console.warn("annotate error", e);
      }
    }

    if (typeof f.start === "number") {
      lastStart = f.start;
    }
  }

  if (skipped) notifyWarn(`Skipped ${skipped} overlaps`);
  console.log("panel:annotate", {
    total: findings.length,
    deduped: deduped.length,
    skipped_overlaps: skipped,
    will_annotate: list.length - skipped,
  });
}

g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;

export async function applyOpsTracked(
  ops: { start: number; end: number; replacement: string }[]
) {
  if (!ops || !ops.length) return;
  const last: string = (window as any).__lastAnalyzed || "";

  await Word.run(async ctx => {
    const body = ctx.document.body;
    (ctx.document as any).trackRevisions = true;

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
        try { target.insertComment("AI edit"); } catch {}
      } else {
        console.warn("[applyOpsTracked] match not found", { snippet, occIdx });
      }
      await ctx.sync();
    }
  });
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


async function onUseWholeDoc() {
  const src = $(Q.original);
  const raw = await getWholeDocText();
  const text = normalizeText(raw || "");
  if (src) {
    src.value = text;
    src.dispatchEvent(new Event("input", { bubbles: true }));
  }
  (window as any).__lastAnalyzed = text;
  (window as any).toast?.("Whole doc loaded");
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
    if (!lastCid) { notifyWarn("Analyze first"); return; }
    const json: any = await postJSON(`${getBackend()}/api/gpt-draft`, { cid: lastCid, clause: text, mode });
    const proposed = (json?.proposed_text ?? json?.draft_text ?? "").toString();

    if (dst) {
      if (!dst.id) dst.id = "proposedText";
      if (!dst.name) dst.name = "proposed";
      (dst as any).dataset.role = "proposed-text";
      dst.value = proposed;
      dst.dispatchEvent(new Event("input", { bubbles: true }));
      notifyOk("Draft ready");
      onDraftReady(proposed);
    } else {
      notifyWarn("Proposed textarea not found");
      onDraftReady('');
    }
  } catch (e) {
    notifyWarn("Draft error");
    console.error(e);
    onDraftReady('');
  }
}

async function doHealth() {
  try {
    const prev = getStoredSchema();
    const resp = await fetch(`${getBackend()}/health`, { method: 'GET' });
    const json: any = await resp.json().catch(() => ({}));
    const schema = resp.headers.get('x-schema-version') || json?.schema || null;
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
        status: json?.status || null,
      });
    } catch {}
    notifyOk(`Health: ${json?.status || 'ok'}${schema ? ` (schema ${schema})` : ''}`);
  } catch (e) {
    setConnBadge(false);
    notifyWarn('Health failed');
    console.error(e);
  }
}

async function doAnalyze() {
  try {
    onDraftReady('');
    const cached = (window as any).__lastAnalyzed as string | undefined;
    const base = cached && cached.trim() ? cached : normalizeText(await (globalThis as any).getWholeDocText());
    if (!base) { notifyErr("В документе нет текста"); return; }

    ensureHeaders();

    (window as any).__lastAnalyzed = base;

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'x-api-key': getStoredKey(),
      'x-schema-version': getStoredSchema(),
    };
    const resp = await fetch(`${getBackend()}/api/analyze`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ text: base }),
    });
    const respSchema = resp.headers.get('x-schema-version');
    if (respSchema) setStoredSchema(respSchema);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json: any = await resp.json();
    if (json?.schema) setStoredSchema(json.schema);
    lastCid = resp.headers.get('x-cid') || '';
    renderResults(json);

    try {
      const all = (globalThis as any).parseFindings(json);
      const thr = getRiskThreshold();
      const filtered = filterByThreshold(all, thr);
      if (isAddCommentsOnAnalyzeEnabled() && filtered.length) {
        await (globalThis as any).annotateFindingsIntoWord(filtered);
      }
    } catch (e) {
      console.warn("auto-annotate after analyze failed", e);
    }

    (document.getElementById("results") || document.body)
      .dispatchEvent(new CustomEvent("ca.results", { detail: json }));

    notifyOk("Analyze OK");
  } catch (e) {
    notifyWarn("Analyze failed");
    console.error(e);
  }
}

async function doQARecheck() {
  ensureHeaders();
  const text = await getWholeDocText();
  const json: any = await postJSON(`${getBackend()}/api/qa-recheck`, { text, rules: {} });
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
  const ok = !json?.error;
  if (ok) {
    notifyOk("QA recheck OK");
  } else {
    const msg = json?.error || json?.message || 'unknown';
    notifyErr(`QA recheck failed: ${msg}`);
  }
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

async function onAcceptAll() {
  try {
    const dst = $(Q.proposed);
    const proposed = (dst?.value || "").trim();
    if (!proposed) { (window as any).toast?.("Nothing to accept"); return; }

    const cid = (document.getElementById("cid")?.textContent || "").trim();
    const base = (() => {
      try { return (localStorage.getItem("backendUrl") || "https://localhost:9443").replace(/\/+$/, ""); }
      catch { return "https://localhost:9443"; }
    })();
    const link = cid && cid !== "—" ? `${base}/api/trace/${cid}` : "AI draft";

    await Word.run(async ctx => {
      const range = ctx.document.getSelection();
      (ctx.document as any).trackRevisions = true;
      range.insertText(proposed, "Replace");
      try { range.insertComment(link); } catch {}
      await ctx.sync();
    });

    (window as any).toast?.("Accepted into Word");
    console.log("[OK] Accepted into Word");
  } catch (e) {
    (window as any).toast?.("Accept failed");
    console.error(e);
  }
}

async function onRejectAll() {
  try {
    const dst = $(Q.proposed);
    if (dst) {
      dst.value = "";
      dst.dispatchEvent(new Event("input", { bubbles: true }));
      onDraftReady('');
    }
    await Word.run(async ctx => {
      const range = ctx.document.getSelection();
      const revs = range.revisions;
      revs.load("items");
      await ctx.sync();
      (revs.items || []).forEach(r => { try { r.reject(); } catch {} });
      await ctx.sync();
    });
    (window as any).toast?.("Rejected");
    console.log("[OK] Rejected");
  } catch (e) {
    (window as any).toast?.("Reject failed");
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
    const data = (window as any).__last?.analyze?.json || {};
    const findings = (globalThis as any).parseFindings(data);
    (globalThis as any).annotateFindingsIntoWord(findings);
  });

  onDraftReady('');
  wireResultsToggle();
  console.log("Panel UI wired");
  ensureHeaders();
}

g.wireUI = g.wireUI || wireUI;

function onDraftReady(text: string) {
  const btn = document.getElementById('btnInsertIntoWord') as HTMLButtonElement;
  const show = !!text.trim();
  btn.style.display = show ? 'inline-block' : 'none';
  btn.disabled = !show;
}

async function onInsertIntoWord() {
  const dst = $(Q.proposed);
  const txt = (dst?.value || "").trim();
  if (!txt) { notifyWarn("No draft to insert"); return; }
  try {
    await insertIntoWord(txt);
    notifyOk("Inserted into Word");
  } catch (e) {
    console.error(e);
    await navigator.clipboard?.writeText(txt).catch(() => {});
    notifyWarn("Insert failed; draft copied to clipboard");
  }
}

async function insertIntoWord(text: string) {
  const w: any = window as any;
  if (w?.Office?.context?.document?.setSelectedDataAsync) {
    await new Promise<void>((resolve, reject) =>
      w.Office.context.document.setSelectedDataAsync(
        text,
        { coercionType: w.Office.CoercionType.Text },
        (res: any) =>
          res?.status === w.Office.AsyncResultStatus.Succeeded ? resolve() : reject(res?.error),
      ),
    );
  } else {
    await navigator.clipboard?.writeText(text).catch(() => {});
    alert('Draft copied to clipboard (Office not ready). Paste it into the document.');
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
