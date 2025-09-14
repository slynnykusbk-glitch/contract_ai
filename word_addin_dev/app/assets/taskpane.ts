import { applyMetaToBadges, parseFindings as apiParseFindings, AnalyzeFinding, AnalyzeResponse, postRedlines, postJSON, analyze } from "./api-client.ts";
import domSchema from "../panel_dom.schema.json";
import { normalizeText, dedupeFindings, severityRank } from "./dedupe.ts";
export { normalizeText, dedupeFindings } from "./dedupe.ts";
import {
  getApiKeyFromStore,
  getSchemaFromStore,
  getAddCommentsFlag,
  setAddCommentsFlag,
  setSchemaVersion,
  setApiKey,
} from "./store.ts";
import { supports, logSupportMatrix } from './supports.ts';
import { registerUnloadHandlers, wasUnloaded, resetUnloadFlag, withBusy } from './pending.ts';
import { checkHealth } from './health.ts';
import { runStartupSelftest } from './startup.selftest.ts';

declare const Violins: { initAudio: () => void };

// enable rich debug when OfficeExtension is available
const gg: any = (globalThis as any);
const oe: any = gg.OfficeExtension;
const BUILD_ID = 'build-20250912-195756';
console.log('ContractAI build', BUILD_ID);
let __cfg_timeout: string | null = null;
let __cfg_abort_hidden = '1';
let __cfg_abort_nav = '1';
try {
  __cfg_timeout = localStorage.getItem('cai_timeout_ms:analyze');
  __cfg_abort_hidden = localStorage.getItem('cai_abort_on_hidden') || '1';
  __cfg_abort_nav = localStorage.getItem('cai_abort_on_navigation') || '1';

} catch {}
console.log('[CFG]', { timeout_analyze: __cfg_timeout, abort_on_hidden: __cfg_abort_hidden, abort_on_navigation: __cfg_abort_nav });
if (!BUILD_ID.includes('build-') && typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', () => {
    try {
      const banner = document.createElement('div');
      banner.textContent = 'FATAL: stale bundle';
      banner.style.padding = '12px';
      banner.style.color = '#f66';
      document.body.innerHTML = '';
      document.body.appendChild(banner);
      document.querySelectorAll('button').forEach(btn => {
        (btn as HTMLButtonElement).disabled = true;
      });
    } catch {}
  });
}
const ENV_MODE = (() => {
  const env = gg.ENV_MODE || (typeof process !== 'undefined' ? (process as any).env?.ENV_MODE : undefined);
  if (env) return env === 'dev' ? 'dev' : 'prod';
  const nodeEnv = typeof process !== 'undefined' ? (process as any).env?.NODE_ENV : undefined;
  return nodeEnv === 'development' ? 'dev' : 'prod';
})();
if (oe && oe.config && (ENV_MODE === 'dev' || gg.__ENABLE_EXTENDED_LOGS__)) {
  // @ts-ignore
  oe.config.extendedErrorLogging = true;
}

export function logRichError(e: any, tag = "Word") {
  try {
    const di = (e && e.debugInfo) || {};
    console.error(`[${tag}] RichApi error`, {
      code: e.code,
      message: e.message,
      errorLocation: di.errorLocation,
      statements: di.statements,
      traceMessages: di.traceMessages,
      inner: di.innerError,
    });
  } catch {}
}

function parseFindings(resp: AnalyzeResponse): AnalyzeFinding[] {
  const arr = apiParseFindings(resp) || [];
  return arr
    .filter(f => f && f.rule_id && f.snippet)
    .map(f => ({ ...f, clause_type: f.clause_type || 'Unknown' }))
    .filter(f => f.clause_type);
}

const g: any = globalThis as any;
g.parseFindings = g.parseFindings || parseFindings;
g.applyMetaToBadges = g.applyMetaToBadges || applyMetaToBadges;
g.getApiKeyFromStore = g.getApiKeyFromStore || getApiKeyFromStore;
g.getSchemaFromStore = g.getSchemaFromStore || getSchemaFromStore;
g.logRichError = g.logRichError || logRichError;
import { notifyOk, notifyErr, notifyWarn } from "./notifier.ts";
import { getWholeDocText } from "./office.ts"; // у вас уже есть хелпер; если имя иное — поправьте импорт.
g.getWholeDocText = g.getWholeDocText || getWholeDocText;

type Mode = "live" | "friendly" | "doctor";
let currentMode: Mode = 'live';

const Q = {
  proposed: 'textarea#proposedText, textarea#draftText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea#originalText, textarea[name="original"], textarea[data-role="original-clause"]'
};

let lastCid: string = "";
let analyzeBound = false;
const REQUIRED_IDS: string[] = (domSchema as any).required_ids || [];

function updateStatusChip(schema?: string | null, cid?: string | null) {
  const el = document.getElementById('status-chip');
  if (!el) return;
  const s = (schema ?? getSchemaFromStore()) || '—';
  const c = (cid ?? lastCid) || '—';
  el.textContent = `schema: ${s} | cid: ${c}`;
}

function enableAnalyze() {
  if (analyzeBound) return;
  bindClick("#btnAnalyze", doAnalyze);
  const btn = document.getElementById("btnAnalyze") as HTMLButtonElement | null;
  if (btn) btn.disabled = false;
  analyzeBound = true;
  console.log('[PANEL] analyze enabled');
}

function getBackend(): string {
  try {
    return (
      localStorage.getItem('backend.url') ||
      localStorage.getItem('backendUrl') ||
      'https://localhost:9443'
    ).replace(/\/+$/, '');
  } catch {
    return 'https://localhost:9443';
  }
}

function onSaveBackend() {
  const inp = document.getElementById('backendUrl') as HTMLInputElement | null;
  const val = inp?.value?.trim();
  if (val) {
    try {
      localStorage.setItem('backend.url', val);
      localStorage.setItem('backendUrl', val);
    } catch {}
  }
  location.reload();
}

function ensureHeaders(): boolean {
  try {
    let apiKey = getApiKeyFromStore();
    let schema = getSchemaFromStore();
    const warn = document.getElementById('hdrWarn') as HTMLElement | null;
    const host = (globalThis as any)?.location?.hostname ?? '';
    const isDev = host === 'localhost' || host === '127.0.0.1';

    if (isDev) {
      if (!apiKey) {
        apiKey = 'local-test-key-123';
        setApiKey(apiKey);
      }
      if (!schema) {
        const envSchema =
          (globalThis as any)?.SCHEMA_VERSION ||
          (typeof process !== 'undefined' && (process as any).env?.SCHEMA_VERSION) ||
          '1.4';
        schema = String(envSchema);
        setSchemaVersion(schema);
      }
    }

    if (warn) {
      if (!apiKey && !schema && !isDev) {
        warn.style.display = '';
      } else {
        warn.style.display = 'none';
      }
    }

    if (!apiKey || !schema) {
      console.warn('missing headers', { apiKey: !!apiKey, schema: !!schema });
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

export function getRiskThreshold(): "low" | "medium" | "high" {
  const sel = document.getElementById("selectRiskThreshold") as HTMLSelectElement | null;
  const v = sel?.value?.toLowerCase();
  return (v === "low" || v === "medium" || v === "high") ? v : "medium";
}

export function isAddCommentsOnAnalyzeEnabled(): boolean {
  const val = getAddCommentsFlag();
  try {
    const doc: any = (globalThis as any).document;
    const cb = (doc?.getElementById("cai-comment-on-analyze") as HTMLInputElement | null)
      || (doc?.getElementById("chkAddCommentsOnAnalyze") as HTMLInputElement | null);
    if (cb) cb.checked = val;
    return cb ? !!cb.checked : val;
  } catch {
    return val;
  }
}

export function setAddCommentsOnAnalyze(val: boolean): void {
  setAddCommentsFlag(val);
}

function isDryRunAnnotateEnabled(): boolean {
  const cb = document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null;
  return cb ? !!cb.checked : false;
}

function filterByThreshold(list: AnalyzeFinding[], thr: "low" | "medium" | "high"): AnalyzeFinding[] {
  const min = severityRank(thr);
  return (list || [])
    .filter(f => f && f.rule_id && f.snippet)
    .map(f => ({ ...f, clause_type: f.clause_type || 'Unknown' }))
    .filter(f => severityRank(f.severity) >= min);
}

function buildLegalComment(f: AnalyzeFinding): string {
  if (!f || !f.rule_id || !f.snippet) {
    console.warn("buildLegalComment: missing required fields", f);
    return "";
  }
  const sev = (f.severity || "info").toUpperCase();
  const rid = f.rule_id;
  const ct = f.clause_type ? ` (${f.clause_type})` : "";
  const advice = f.advice || "—";
  const law = Array.isArray(f.law_refs) && f.law_refs.length ? f.law_refs.join('; ') : "—";
  const conflict = Array.isArray(f.conflict_with) && f.conflict_with.length ? f.conflict_with.join('; ') : "—";
  const fix = f.suggestion?.text || '—';
  const citations = Array.isArray(f.citations) && f.citations.length ? `\nCitations: ${f.citations.join('; ')}` : '';
  return `[${sev}] ${rid}${ct}\nReason: ${advice}\nLaw: ${law}\nConflict: ${conflict}${citations}\nSuggested fix: ${fix}`;
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
    logRichError(e, "findings");
    console.warn("mapFindingToRange fail", e);
    return null;
  }
}

export async function annotateFindingsIntoWord(findings: AnalyzeFinding[]): Promise<number> {
  return withBusy(async () => {
  const cb = document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null;
  function isDryRunAnnotateEnabled() {
    if (cb) return !!cb.checked;
    return !!(document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null)?.checked;
  }
  const base = normalizeText((window as any).__lastAnalyzed || "");

  // 1) валидируем, чистим и сортируем с защитой от overlaps
  const deduped = dedupeFindings(findings || []);
  const sorted = deduped.slice().sort((a, b) => (b.end ?? 0) - (a.end ?? 0));

  const todo: AnalyzeFinding[] = [];
  let lastStart = Number.POSITIVE_INFINITY;
  let skipped = 0;
  for (const f of sorted) {
    if (!f || !f.rule_id || !f.snippet) { skipped++; continue; }
    const snippet = f.snippet;
    const end = typeof f.end === "number" ? f.end : (typeof f.start === "number" ? f.start + snippet.length : undefined);
    if (typeof end === "number" && end > lastStart) { skipped++; continue; }
    todo.push(f);
    if (typeof f.start === "number") lastStart = f.start;
  }
  if (skipped) notifyWarn(`Skipped ${skipped} overlaps/invalid`);
  notifyOk(`Will insert: ${todo.length}`);

  // 2) готовим элементы + индекс вхождения (чтобы попадать в нужный occurrence)
  const items = todo.map(f => {
    const raw = f.snippet || "";
    const norm = normalizeText(raw);
    const occIdx = nthOccurrenceIndex(base, norm, f.start);
    return {
      raw,
      norm,
      msg: buildLegalComment(f),
      rule_id: f.rule_id,
      occIdx,
      normalized_fallback: normalizeText((f as any).normalized_snippet || "")
    };
  });

  // 3) СЕРИЙНАЯ вставка: один Word.run на одну цель (чтобы не ловить InvalidObjectPath)
  const searchOpts = { matchCase: false, matchWholeWord: false } as Word.SearchOptions;
  let inserted = 0;


  for (const it of items) {
    await Word.run(async ctx => {
      const body = ctx.document.body;

      // primary: raw текст
      let target: Word.Range | null = null;
      const sRaw = body.search(it.raw, searchOpts);
      sRaw.load("items");
      await ctx.sync();


      const pick = (coll: Word.RangeCollection | undefined | null, occ: number): Word.Range | null => {
        const arr = coll?.items || [];
        if (!arr.length) return null;
        return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
      };
      target = pick(sRaw, it.occIdx);

      // fallback #1: нормализованный текст из finding (если есть и отличается)
      if (!target) {
        const fb = it.normalized_fallback && it.normalized_fallback !== it.norm ? it.normalized_fallback : it.norm;
        if (fb && fb.trim()) {
          const sNorm = body.search(fb, searchOpts);
          sNorm.load("items");
          await ctx.sync();
          target = pick(sNorm, it.occIdx);
        }
      }

      // fallback #2: длинный токен (самое длинное слово/фраза) из raw
      if (!target) {
        const token = (() => {
          const tks = it.raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter(x => x.length >= 12);
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

      // вставка / dry-run select
      if (target) {
        if (isDryRunAnnotateEnabled()) {
          try { target.select(); } catch {}
        } else if (it.msg) {
          target.insertComment(it.msg);
        }
        inserted++;
      } else {
        console.warn("[annotate] no match for snippet", { rid: it.rule_id, snippet: it.raw.slice(0, 120) });
      }

      await ctx.sync();
    }).catch(e => {
      logRichError(e, "annotate");
      console.warn("annotate run fail", e?.code, e?.message, e?.debugInfo);
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
  });
}


g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;

async function onClearAnnots() {
  try {
    await Word.run(async ctx => {
      const body = ctx.document.body;
      const cmts = ctx.document.comments;
      cmts.load('items');
      await ctx.sync();
      for (const c of cmts.items) {
        try { c.delete(); } catch {}
      }
      try { body.font.highlightColor = "NoColor" as any; } catch {}
      await ctx.sync();
    });
    notifyOk('Annotations cleared');
  } catch (e) {
    logRichError(e, 'annotate');
    notifyWarn('Failed to clear annotations');
  }
}

export async function applyOpsTracked(
  ops: { start: number; end: number; replacement: string; context_before?: string; context_after?: string; rationale?: string; source?: string }[]
) {
  return withBusy(async () => {
  let cleaned = (ops || [])
    .filter(o => typeof o.start === "number" && typeof o.end === "number" && o.end > o.start)
    .sort((a, b) => a.start - b.start);

  // prune overlaps keeping earlier ops
  let lastEnd = -1;
  cleaned = cleaned.filter(o => {
    if (o.start < lastEnd) return false;
    lastEnd = o.end;
    return true;
    });

  if (!cleaned.length) return;
  const last: string = (window as any).__lastAnalyzed || "";

  await Word.run(async ctx => {
    const body = ctx.document.body;
    (ctx.document as any).trackRevisions = true;
    const searchOpts = { matchCase: false, matchWholeWord: false } as Word.SearchOptions;

    const pick = (coll: Word.RangeCollection | undefined | null, occ: number): Word.Range | null => {
      const arr = coll?.items || [];
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

      let target: Word.Range | null = null;

      if (op.context_before || op.context_after) {
        const searchText = `${op.context_before || ''}${snippet}${op.context_after || ''}`;
        const sFull = body.search(searchText, searchOpts);
        sFull.load('items');
        await ctx.sync();
        const fullRange = pick(sFull, occIdx);
        if (fullRange) {
          const inner = fullRange.search(snippet, searchOpts);
          inner.load('items');
          await ctx.sync();
          target = pick(inner, 0);
        }
      }

      if (!target) {
        const found = body.search(snippet, searchOpts);
        found.load('items');
        await ctx.sync();
        target = pick(found, occIdx);
      }

      if (!target) {
        const token = (() => {
          const tks = snippet.replace(/[^\p{L}\p{N} ]/gu, ' ').split(' ').filter(x => x.length >= 12);
          if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
          return null;
        })();
        if (token) {
          const sTok = body.search(token, searchOpts);
          sTok.load('items');
          await ctx.sync();
          target = pick(sTok, 0);
        }
      }

      if (target) {

        target.insertText(op.replacement, 'Replace');
        const comment = op.rationale || op.source || 'AI edit';
        try { target.insertComment(comment); } catch {}
      } else {
        console.warn('[applyOpsTracked] match not found', { snippet, occIdx });
      }
      await ctx.sync();
    }
  });
  });
}

g.applyOpsTracked = g.applyOpsTracked || applyOpsTracked;



async function highlightFinding(f: AnalyzeFinding) {
  const base = normalizeText((window as any).__lastAnalyzed || "");
  const raw = f?.snippet || "";
  const norm = normalizeText(raw);
  const occIdx = nthOccurrenceIndex(base, norm, f.start);
  const searchOpts = { matchCase: false, matchWholeWord: false } as Word.SearchOptions;

  await Word.run(async ctx => {
    const body = ctx.document.body;
    let target: Word.Range | null = null;
    const pick = (coll: Word.RangeCollection | undefined | null, occ: number): Word.Range | null => {
      const arr = coll?.items || [];
      if (!arr.length) return null;
      return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
    };

    const sRaw = body.search(raw, searchOpts);
    sRaw.load("items");
    await ctx.sync();
    target = pick(sRaw, occIdx);

    if (!target) {
      const fb = (f as any).normalized_snippet && (f as any).normalized_snippet !== norm ? (f as any).normalized_snippet : norm;
      if (fb && fb.trim()) {
        const sNorm = body.search(fb, searchOpts);
        sNorm.load("items");
        await ctx.sync();
        target = pick(sNorm, occIdx);
      }
    }

    if (!target) {
      const token = (() => {
        const tks = raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter(x => x.length >= 12);
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
      try { target.select(); } catch {}
    }
    await ctx.sync();
  });
}

async function navigateFinding(dir: number) {
  const arr: AnalyzeFinding[] = (window as any).__findings || [];
  if (!arr.length) return;
  const w: any = window as any;
  w.__findingIdx = (w.__findingIdx ?? 0) + dir;
  if (w.__findingIdx < 0) w.__findingIdx = arr.length - 1;
  if (w.__findingIdx >= arr.length) w.__findingIdx = 0;
  const list = document.getElementById("findingsList");
  if (list) {
    const items = Array.from(list.querySelectorAll("li"));
    items.forEach((li, i) => {
      (li as HTMLElement).classList.toggle("active", i === w.__findingIdx);
    });
    const act = items[w.__findingIdx] as HTMLElement | undefined;
    if (act) act.scrollIntoView({ block: "nearest" });
  }
  try { await highlightFinding(arr[w.__findingIdx]); } catch {}
}

function onPrevIssue() { navigateFinding(-1); }
function onNextIssue() { navigateFinding(1); }

export function renderAnalysisSummary(json: any) {
  // аккуратно вытаскиваем ключевые поля
  const clauseType =
    json?.summary?.clause_type ||
    json?.meta?.clause_type ||
    json?.doc_type ||
    "—";

  const findings = Array.isArray(json?.findings) ? json.findings : [];
  const recs = Array.isArray(json?.recommendations) ? json.recommendations : [];

  const thr = getRiskThreshold();
  const visibleFindings = filterByThreshold(findings, thr);
  const visible = visibleFindings.length;
  const hidden = findings.length - visible;

  const setText = (id: string, val: string) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setText("clauseTypeOut", String(clauseType));
  setText("resFindingsCount", String(findings.length));
  setText("visibleHiddenOut", `${visible} / ${hidden}`);

  // Заполняем findings
  const fCont = document.getElementById("findingsList");
  if (fCont) {
    fCont.innerHTML = "";
    for (const f of findings) {
      const li = document.createElement("li");
      const title =
        f?.title || f?.finding?.title || f?.rule_id || "Issue";
      const snippet = f?.snippet || f?.evidence?.text || "";
      li.textContent = snippet ? `${title}: ${snippet}` : String(title);
      fCont.appendChild(li);
    }
  }

  // Заполняем рекомендации
  const rCont = document.getElementById("recsList");
  if (rCont) {
    rCont.innerHTML = "";
    for (const r of recs) {
      const li = document.createElement("li");
      li.textContent = r?.text || r?.advice || r?.message || "Recommendation";
      rCont.appendChild(li);
    }
  }

  // Показать блок результатов (если был скрыт стилями)
  const rb = document.getElementById("resultsBlock") as HTMLElement | null;
  if (rb) rb.style.removeProperty("display");
}

function renderResults(res: any) {
  const clause = slot("resClauseType", "clause-type");
  if (clause) clause.textContent = res?.clause_type || "—";

  const findingsArr: AnalyzeFinding[] = parseFindings(res);
  (window as any).__findings = findingsArr;
  (window as any).__findingIdx = 0;
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
    logRichError(e, "findings");
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
    try { src.dispatchEvent(new Event("input", { bubbles: true })); } catch {}
  }
  const hid = document.getElementById("originalText") as HTMLTextAreaElement | null;
  if (hid && hid !== src) {
    hid.value = text;
    try { hid.dispatchEvent(new Event("input", { bubbles: true })); } catch {}
  }
  (window as any).__lastAnalyzed = text;
  (window as any).toast?.("Whole doc loaded");
}

async function onSuggestEdit(ev?: Event) {
  return withBusy(async () => {
    try {
      const dst = $(Q.proposed);
      const base = (window as any).__lastAnalyzed || normalizeText(await getWholeDocText());
      if (!base) { notifyWarn("No document text"); return; }
      const arr: AnalyzeFinding[] = (window as any).__findings || [];
      const idx = (window as any).__findingIdx ?? 0;
      const finding = arr[idx];
      if (!finding) { notifyWarn("No active finding"); return; }
      const clause = finding.snippet || '';
      const { json } = await postJSON('/api/gpt-draft', { cid: lastCid, clause, mode: 'friendly' });
      const proposed = (json?.proposed_text ?? json?.text ?? "").toString();
      const w: any = window as any;
      w.__last = w.__last || {};
      w.__last['gpt-draft'] = { json };
      if (dst) {
        if (!dst.id) dst.id = "draftText";
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
  });
}

async function doHealth() {
  try {
    const prev = getSchemaFromStore();
    const { resp, json, ok } = await checkHealth({ backend: getBackend() });
    const schema = resp.headers.get('x-schema-version') || json?.schema || null;
    if (schema) {
      setSchemaVersion(schema);
      if (schema !== prev) {
        console.log(`schema: ${schema} (synced)`);
      }
    }
    setConnBadge(ok);
    if (ok) {
      console.log('[PANEL] health ok');
      enableAnalyze();
      updateStatusChip(schema, null);
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
    } else {
      notifyWarn('Health failed');
    }
  } catch (e) {
    setConnBadge(false);
    notifyWarn('Health failed');
    console.error(e);
  }
}

async function doAnalyze() {
  return withBusy(async () => {
    const btn = document.getElementById("btnAnalyze") as HTMLButtonElement | null;
    const busy = document.getElementById("busyBar") as HTMLElement | null;
    if (btn) btn.disabled = true;
    if (busy) busy.style.display = "";
    try {
      onDraftReady('');
      const cached = (window as any).__lastAnalyzed as string | undefined;
      const base = cached && cached.trim() ? cached : normalizeText(await (globalThis as any).getWholeDocText());
      if (!base) { notifyErr("В документе нет текста"); return; }

      ensureHeaders();

      (window as any).__lastAnalyzed = base;
      const orig = document.getElementById("originalText") as HTMLTextAreaElement | null;
      if (orig) orig.value = base;

      const { resp, json } = await analyze({ text: base, mode: currentMode });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const respSchema = resp.headers.get('x-schema-version');
      if (respSchema) setSchemaVersion(respSchema);
      if (json?.schema) setSchemaVersion(json.schema);
      lastCid = resp.headers.get('x-cid') || '';
      updateStatusChip(null, lastCid);
      renderResults(json);
      renderAnalysisSummary(json);

      try { localStorage.setItem('last_analysis_json', JSON.stringify(json)); } catch {}

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
    } catch (e: any) {
      let tail = '';
      if (e?.name === 'AbortError') {
        const msg = e?.message || '';
        if (msg.startsWith('timeout')) {
          const ms = parseInt(msg.replace(/[^0-9]/g, ''), 10) || 0;
          tail = `(timeout ${Math.round(ms / 1000)} s)`;
        } else if (msg === 'pagehide/unload') {
          tail = '(aborted by pagehide)';
        } else {
          tail = '(aborted)';
        }
      } else if (typeof e?.message === 'string') {
        if (e.message.includes('HTTP 504')) tail = '(HTTP 504)';
        else if (e.message.includes('HTTP 413')) tail = '(payload too large 413)';
        else if (e.message.includes('HTTP 401')) tail = '(unauthorized 401)';
        else if (e.message.includes('HTTP 403')) tail = '(forbidden 403)';
        else if (e.message.includes('HTTP 422')) tail = '(schema mismatch 422)';
      }
      notifyWarn(`Analyze failed ${tail}`.trim());
      console.error(e);
    } finally {
      if (btn) btn.disabled = false;
      if (busy) busy.style.display = "none";
    }
  });
}

async function doQARecheck() {
  return withBusy(async () => {
    ensureHeaders();
    const text = await getWholeDocText();
    const { json } = await postJSON('/api/qa-recheck', { text, rules: {} });
    (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
    const ok = !json?.error;
    if (ok) {
      notifyOk("QA recheck OK");
    } else {
      const msg = json?.error || json?.message || 'unknown';
      notifyErr(`QA recheck failed: ${msg}`);
    }
  });
}

function bindClick(sel: string, fn: () => void) {
  const el = document.querySelector(sel) as HTMLButtonElement | null;
  if (!el) return;
  el.addEventListener("click", (e) => { e.preventDefault(); fn(); });
  el.classList.remove("js-disable-while-busy");
  el.removeAttribute("disabled");
}

async function onPreviewDiff() {
  try {
    const before = (window as any).__lastAnalyzed || '';
    const after = ($(Q.proposed)?.value || '').trim();
    if (!after) { notifyWarn('No draft to diff'); return; }
    const diff: any = await postRedlines(before, after);
    const html = diff?.json?.html || diff?.json?.diff_html || diff?.json?.redlines || '';
    const out = document.getElementById('diffOutput') as HTMLElement | null;
    const cont = document.getElementById('diffContainer') as HTMLElement | null;
    if (out && cont) {
      out.innerHTML = html || '';
      cont.style.display = html ? 'block' : 'none';
    }
  } catch (e) {
    notifyWarn('Diff failed');
    console.error(e);
  }
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
      range.insertText(proposed, Word.InsertLocation.replace);
      try { range.insertComment(link); } catch {}
      await ctx.sync();
    });

    (window as any).toast?.("Accepted into Word");
    console.log("[OK] Accepted into Word");
  } catch (e) {
    (window as any).toast?.("Accept failed");
    logRichError(e, "insertDraft");
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
    logRichError(e, "insertDraft");
    console.error(e);
  }
}

export function wireUI() {
  console.log('[PANEL] wireUI start');
  if (!(globalThis as any).__CAI_TESTING__) {
    const missing = REQUIRED_IDS.filter(id => !document.getElementById(id));
    if (missing.length) {
      console.error('[PANEL] wireUI missing IDs:', missing);
      const msg = `FATAL: panel template mismatch (missing: ${missing.join(', ')}). Check build pipeline.`;
      try {
        const banner = document.createElement ? document.createElement('div') : null;
        if (banner) {
          banner.textContent = msg;
          banner.style.padding = '12px';
          banner.style.color = '#f66';
          document.body.innerHTML = '';
          document.body.appendChild(banner);
        }
      } catch {}
      console.error(msg);
      return;
    }
  }

  const bookEl = document.getElementById('loading-book');
  window.addEventListener('cai:busy', (e: any) => {
    if (!bookEl) return;
    const busy = !!(e?.detail?.busy);
    if (busy) bookEl.classList.remove('hidden');
    else bookEl.classList.add('hidden');
  });

  const s = logSupportMatrix();
  const disable = (id: string) => {
    const el = document.getElementById(id) as HTMLButtonElement | null;
    if (el) { el.disabled = true; el.title = 'Not supported'; }
  };

  bindClick("#btnUseWholeDoc", onUseWholeDoc);
  const wholeBtn = document.getElementById('btnUseWholeDoc') as HTMLButtonElement | null;
  if (wholeBtn) wholeBtn.disabled = false;
  if (ENV_MODE === 'dev') bindClick("#btnTest", doHealth);
  else {
    const bt = document.getElementById('btnTest');
    if (bt) (bt as HTMLElement).style.display = 'none';
  }
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnSuggestEdit")?.addEventListener("click", onSuggestEdit);
  bindClick("#btnApplyTracked", onApplyTracked);
  bindClick("#btnAcceptAll", onAcceptAll);
  bindClick("#btnRejectAll", onRejectAll);
  bindClick("#btnPrevIssue", onPrevIssue);
  bindClick("#btnNextIssue", onNextIssue);
  bindClick("#btnPreviewDiff", onPreviewDiff);
  bindClick("#btnClearAnnots", onClearAnnots);
  bindClick("#btnSave", onSaveBackend);
  const cb = (document.getElementById("cai-comment-on-analyze") as HTMLInputElement | null)
    || (document.getElementById("chkAddCommentsOnAnalyze") as HTMLInputElement | null);
  if (cb) {
    cb.checked = isAddCommentsOnAnalyzeEnabled();
    cb.addEventListener("change", () => setAddCommentsOnAnalyze(!!cb.checked));
  } else {
    isAddCommentsOnAnalyzeEnabled();
  }
  const annotateBtn = document.getElementById("btnAnnotate") as HTMLButtonElement | null;
  if (annotateBtn) {
    annotateBtn.addEventListener("click", async () => {
      if (annotateBtn.disabled) return;
      annotateBtn.disabled = true;
      try {
        const data = (window as any).__last?.analyze?.json || {};
        const findings = (globalThis as any).parseFindings(data);
        await (globalThis as any).annotateFindingsIntoWord(findings);
      } finally {
        annotateBtn.disabled = false;
      }
    });
    annotateBtn.classList.remove("js-disable-while-busy");
    annotateBtn.removeAttribute("disabled");
  }

  onDraftReady('');
  wireResultsToggle();
  console.log("Panel UI wired");
  const ab = document.getElementById("btnAnalyze") as HTMLButtonElement | null;
  if (ab) ab.disabled = true;
  ensureHeaders();
  updateStatusChip();

  if (!s.revisions) { disable('btnApplyTracked'); disable('btnAcceptAll'); disable('btnRejectAll'); }
  if (!s.comments) { disable('btnAcceptAll'); }
  if (!s.search) { disable('btnPrevIssue'); disable('btnNextIssue'); disable('btnQARecheck'); }
  if (!s.contentControls) { disable('btnAnnotate'); }
  if (!s.revisions || !s.comments || !s.search || !s.contentControls) {
    try { setOfficeBadge('Word ⚠'); } catch {}
  }
}

g.wireUI = g.wireUI || wireUI;

// self-test moved to startup.selftest.ts

function onDraftReady(text: string) {
  const show = !!text.trim();
  const apply = document.getElementById('btnApplyTracked') as HTMLButtonElement | null;
  const accept = document.getElementById('btnAcceptAll') as HTMLButtonElement | null;
  const reject = document.getElementById('btnRejectAll') as HTMLButtonElement | null;
  const diff = document.getElementById('btnPreviewDiff') as HTMLButtonElement | null;
  const pane = document.getElementById('draftPane') as HTMLElement | null;
  const dst = document.getElementById('draftText') as HTMLTextAreaElement | null;
  if (dst) dst.value = text;
  if (pane) pane.style.display = show ? '' : 'none';
  if (apply) apply.disabled = !show;
  if (accept) accept.disabled = !show;
  if (reject) reject.disabled = !show;
  if (diff) diff.disabled = !show;
}

async function bootstrap(info?: Office.OfficeInfo) {
  console.log('[PANEL] bootstrap start');
  if (wasUnloaded()) {
    console.log('reopen clean OK');
    resetUnloadFlag();
  }
  wireUI();
  registerUnloadHandlers();
  try { await runStartupSelftest(getBackend()); } catch {}
  try { await doHealth(); } catch {}
  try {
    setOfficeBadge(`${info?.host || Office.context?.host || "Word"} ✓`);
  } catch {
    setOfficeBadge(null);
  }
}

let bootstrapCalls = 0;
export function invokeBootstrap(info?: Office.OfficeInfo) {
  if (wasUnloaded()) {
    bootstrapCalls = 0;
  }
  if (bootstrapCalls > 0) {
    console.log(`bootstrap invoked x${bootstrapCalls+1}`);
    return;
  }
  bootstrapCalls++;
  console.log('bootstrap invoked x1');
  void bootstrap(info);
}
export function getBootstrapCount() { return bootstrapCalls; }

if (!(globalThis as any).__CAI_TESTING__) {
  const launch = () => Office.onReady(info => invokeBootstrap(info));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', launch);
  } else {
    launch();
  }
}
