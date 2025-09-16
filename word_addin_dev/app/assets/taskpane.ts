import { applyMetaToBadges, parseFindings as apiParseFindings, AnalyzeFinding, AnalyzeResponse, postRedlines, analyze, apiQaRecheck } from "./api-client.ts";
import domSchema from "../panel_dom.schema.json";
import { normalizeText, severityRank, dedupeFindings } from "./dedupe.ts";
export { normalizeText, dedupeFindings } from "./dedupe.ts";
import { planAnnotations, annotateFindingsIntoWord, AnnotationPlan, COMMENT_PREFIX, safeInsertComment, fallbackAnnotateWithContentControl } from "./annotate.ts";
import { findAnchors } from "./anchors.ts";
import { safeBodySearch } from "./safeBodySearch.ts";
import { insertDraftText } from "./insert.ts";
import {
  getApiKeyFromStore,
  getSchemaFromStore,
  getAddCommentsFlag,
  setAddCommentsFlag,
  setSchemaVersion,
  setApiKey,
} from "./store.ts";
import { supports, logSupportMatrix } from './supports.ts';
import { registerUnloadHandlers, wasUnloaded, resetUnloadFlag, withBusy, pendingFetches } from './pending.ts';
import { checkHealth } from './health.ts';
import { runStartupSelftest } from './startup.selftest.ts';
import DiffMatchPatch from 'diff-match-patch';

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

function parseFindings(resp: AnalyzeResponse | AnalyzeFinding[]): AnalyzeFinding[] {
  const arr = apiParseFindings(resp as any) || [];
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
import { notifyOk, notifyErr, notifyWarn } from "./notifier";
import { getWholeDocText, getSelectionText } from "./office.ts"; // у вас уже есть хелперы; если имя иное — поправьте импорт.
g.getWholeDocText = g.getWholeDocText || getWholeDocText;
g.getSelectionText = g.getSelectionText || getSelectionText;

// track already processed ranges to avoid reapplying the same ops
const appliedRangeHashes: Set<string> = g.__appliedRangeHashes || new Set<string>();
g.__appliedRangeHashes = appliedRangeHashes;

type Mode = "live" | "friendly" | "doctor";
let currentMode: Mode = 'live';

const Q = {
  proposed: 'textarea#proposedText, textarea#draftText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea#originalText, textarea[name="original"], textarea[data-role="original-clause"]'
};

let lastCid: string = "";
let analyzeBound = false;
let analyzeInProgress = false;
const REQUIRED_IDS: string[] = (domSchema as any).required_ids || [];

export function mustGetElementById<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`missing element #${id}`);
  }
  return el as T;
}

function updateStatusChip(schema?: string | null, cid?: string | null) {
  const el = mustGetElementById<HTMLElement>('status-chip');
  const s = (schema ?? getSchemaFromStore()) || '—';
  const c = (cid ?? lastCid) || '—';
  el.textContent = `schema: ${s} | cid: ${c}`;
}

function updateAnchorBadge() {
  const el = mustGetElementById<HTMLElement>('anchorsBadge');
  const skipped = (globalThis as any).__anchorsSkipped || 0;
  el.style.display = skipped > 0 ? '' : 'none';
}
g.updateAnchorBadge = g.updateAnchorBadge || updateAnchorBadge;

function enableAnalyze() {
  if (analyzeBound) return;
  bindClick("#btnAnalyze", onAnalyze);
  const btn = mustGetElementById<HTMLButtonElement>("btnAnalyze");
  btn.disabled = false;
  analyzeBound = true;
  console.log('[PANEL] analyze enabled');
}

function getBackend(): string {
  try {
    return (
      localStorage.getItem('backend.url') ||
      localStorage.getItem('backendUrl') ||
      'https://127.0.0.1:9443'
    ).replace(/\/+$/, '');
  } catch {
    return 'https://127.0.0.1:9443';
  }
}

function onSaveBackend() {
  const inp = mustGetElementById<HTMLInputElement>('backendUrl');
  const val = inp.value.trim();
  if (val) {
    try {
      localStorage.setItem('backend.url', val);
      localStorage.setItem('backendUrl', val);
    } catch {}
  }
  location.reload();
}

function ensureHeaders(): boolean {
  let apiKey = getApiKeyFromStore();
  let schema = getSchemaFromStore();
  const warn = mustGetElementById<HTMLElement>('hdrWarn');
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

  if (!apiKey && !schema && !isDev) {
    warn.style.display = '';
  } else {
    warn.style.display = 'none';
  }

  if (!apiKey || !schema) {
    console.warn('missing headers', { apiKey: !!apiKey, schema: !!schema });
  }
  return true; // allow all actions regardless of header state
}

function slot(id: string, role: string): HTMLElement {
  const byRole = document.querySelector(`[data-role="${role}"]`) as HTMLElement | null;
  if (byRole) return byRole;
  return mustGetElementById<HTMLElement>(id);
}

export function getRiskThreshold(): "low" | "medium" | "high" {
  const sel = mustGetElementById<HTMLSelectElement>("selectRiskThreshold");
  const v = sel.value.toLowerCase();
  return (v === "low" || v === "medium" || v === "high") ? v : "medium";
}

export function isAddCommentsOnAnalyzeEnabled(): boolean {
  const val = getAddCommentsFlag();
  try {
    const cb = (() => {
      try { return mustGetElementById<HTMLInputElement>("cai-comment-on-analyze"); }
      catch { return mustGetElementById<HTMLInputElement>("chkAddCommentsOnAnalyze"); }
    })();
    cb.checked = val;
    return !!cb.checked;
  } catch {
    return val;
  }
}

export function setAddCommentsOnAnalyze(val: boolean): void {
  setAddCommentsFlag(val);
}

function isDryRunAnnotateEnabled(): boolean {
  const cb = mustGetElementById<HTMLInputElement>("cai-dry-run-annotate");
  return !!cb.checked;
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
  const conflicts = Array.isArray((f as any).links)
    ? (f as any).links.filter((l: any) => l?.type === 'conflict' && l?.targetFindingId).map((l: any) => l.targetFindingId)
    : Array.isArray((f as any).conflict_with) ? (f as any).conflict_with : [];
  const conflict = conflicts.length ? conflicts.join('; ') : "—";
  const fix = f.suggestion?.text || '—';
  const citations = Array.isArray(f.citations) && f.citations.length ? `\nCitations: ${f.citations.join('; ')}` : '';
  return `[${sev}] ${rid}${ct}\nReason: ${advice}\nLaw: ${law}\nConflict: ${conflict}${citations}\nSuggested fix: ${fix}`;
}



g.annotateFindingsIntoWord = g.annotateFindingsIntoWord || annotateFindingsIntoWord;

export async function clearAnnotations() {
  try {
    await Word.run(async ctx => {
      const body = ctx.document.body;
      const cmts: any = (ctx.document as any).comments;
      const found = typeof (body as any).search === 'function'
        ? body.search(COMMENT_PREFIX, { matchCase: false })
        : null;
      if (cmts && typeof cmts.load === 'function') cmts.load('items');
      if (found && typeof found.load === 'function') found.load('items');
      await ctx.sync();
      if (cmts?.items) {
        for (const c of cmts.items) {
          try {
            const txt = (c as any).text || "";
            if (txt.startsWith(COMMENT_PREFIX)) c.delete();
          } catch {}
        }
      }
      if (found?.items && found.items.length) {
        for (const r of found.items) {
          try {
            r.insertText('', Word.InsertLocation.replace);
          } catch {}
        }
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

function diffTokens(before: string, after: string): [number, string][] {
  const dmp = new DiffMatchPatch();
  const tokenize = (s: string) => s.match(/\S+|\s+/g) || [];
  const { chars1, chars2, tokenArray } = tokensToChars(tokenize(before), tokenize(after));
  let diffs = dmp.diff_main(chars1, chars2);
  dmp.diff_cleanupSemantic(diffs);
  return diffs.map(([op, data]) => [op, data.split('').map(ch => tokenArray[ch.charCodeAt(0)]).join('')]);
}

function tokensToChars(tokens1: string[], tokens2: string[]) {
  const tokenArray: string[] = [];
  const tokenHash = new Map<string, number>();
  const toChar = (tok: string) => {
    if (tokenHash.has(tok)) return String.fromCharCode(tokenHash.get(tok)!);
    tokenArray.push(tok);
    tokenHash.set(tok, tokenArray.length - 1);
    return String.fromCharCode(tokenArray.length - 1);
  };
  const chars1 = tokens1.map(toChar).join('');
  const chars2 = tokens2.map(toChar).join('');
  return { chars1, chars2, tokenArray };
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
      const hashKey = `${op.start}:${op.end}:${op.replacement}`;
      if (appliedRangeHashes.has(hashKey)) continue;

      const snippet = last.slice(op.start, op.end);
      const occIdx = (() => {
        let idx = -1, n = 0;
        while ((idx = last.indexOf(snippet, idx + 1)) !== -1 && idx < op.start) n++;
        return n;
      })();

      let target: Word.Range | null = null;

      if (op.context_before || op.context_after) {
        const searchText = `${op.context_before || ''}${snippet}${op.context_after || ''}`;
        const sFull = await safeBodySearch(body, searchText, searchOpts);
        const fullRange = pick(sFull, occIdx);
        if (fullRange) {
          // Clamp snippet before searching to avoid Word's
          // SearchStringInvalidOrTooLong errors (limit ~255 chars).
          const head = snippet.slice(0, 240);
          const tail = snippet.slice(-240);
          const innerStart: any = fullRange.search(head, searchOpts);
          const innerEnd: any = fullRange.search(tail, searchOpts);
          if (innerStart && typeof innerStart.load === 'function') innerStart.load('items');
          if (innerEnd && typeof innerEnd.load === 'function') innerEnd.load('items');
          await ctx.sync();
          const startRange = pick(innerStart, 0);
          const endRange = pick(innerEnd, 0);
          if (startRange && endRange && typeof startRange.expandTo === 'function') {
            target = startRange.expandTo(endRange);
          } else {
            target = startRange;
          }
        }
      }

      if (!target) {
        const found = await safeBodySearch(body, snippet, searchOpts);
        target = pick(found, occIdx);
      }

      if (!target) {
        const token = (() => {
          const tks = snippet.replace(/[^\p{L}\p{N} ]/gu, ' ').split(' ').filter(x => x.length >= 12);
          if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
          return null;
        })();
        if (token) {
          const sTok = await safeBodySearch(body, token, searchOpts);
          target = pick(sTok, 0);
        }
      }

      if (target) {
        const diffs = diffTokens(snippet, op.replacement);
        let cursor = target.getRange('Start');
        for (const [kind, txt] of diffs) {
          if (!txt) continue;
          if (kind === 0) {
            const rest = cursor.getRange('After');
            const foundEq: any = rest.search(txt, searchOpts);
            if (foundEq && typeof foundEq.load === 'function') foundEq.load('items');
            await ctx.sync();
            const eq = pick(foundEq, 0);
            if (eq) cursor = eq.getRange('After');
          } else if (kind === -1) {
            const rest = cursor.getRange('After');
            const foundDel: any = rest.search(txt, searchOpts);
            if (foundDel && typeof foundDel.load === 'function') foundDel.load('items');
            await ctx.sync();
            const del = pick(foundDel, 0);
            if (del) {
              del.insertText('', 'Replace');
              cursor = del.getRange('After');
            }
          } else if (kind === 1) {
            const ins = cursor.insertText(txt, 'Before');
            cursor = ins.getRange('After');
          }
        }
        const comment = `${COMMENT_PREFIX} ${op.rationale || op.source || 'AI edit'}`;
        const res = await safeInsertComment(target, comment);
        if (!res.ok) {
          await fallbackAnnotateWithContentControl(target, comment.replace(COMMENT_PREFIX, "").trim());
        }


      } else {
        console.warn('[applyOpsTracked] match not found', { snippet, occIdx });
      }
      await ctx.sync();
    }
  });
  });
}

g.applyOpsTracked = g.applyOpsTracked || applyOpsTracked;

function clearHighlightInCtx(ctx: Word.RequestContext, w: any) {
  if (w.__highlight) {
    try { w.__highlight.font.highlightColor = 'NoColor' as any; } catch {}
    ctx.trackedObjects.remove(w.__highlight);
    w.__highlight = null;
  }
}

export async function clearHighlight() {
  const w: any = window as any;
  if (!w.__highlight) return;
  await Word.run(async ctx => {
    clearHighlightInCtx(ctx, w);
    await ctx.sync();
  });
}

async function highlightFinding(op: AnnotationPlan) {
  await Word.run(async ctx => {
    const w: any = window as any;
    clearHighlightInCtx(ctx, w);
    const body = ctx.document.body as any;
    let anchors = await findAnchors(body, op.raw);
    let target: any = anchors[Math.min(op.occIdx, anchors.length - 1)] || null;
    if (!target && op.normalized_fallback && op.normalized_fallback !== op.norm) {
      anchors = await findAnchors(body, op.normalized_fallback);
      target = anchors[Math.min(op.occIdx, anchors.length - 1)] || null;
    }
    if (target) {
      w.__highlight = target;
      ctx.trackedObjects.add(target);
      try { target.select(); } catch {}
      try { target.font.highlightColor = '#ffff00' as any; } catch {}
    }
    await ctx.sync();
  });
}

let isNavigating = false;
async function navigateFinding(dir: number) {
  if (isNavigating) return;
  isNavigating = true;
  const arr: AnnotationPlan[] = (window as any).__findings || [];
  if (!arr.length) {
    isNavigating = false;
    return;
  }
  const prevBtn = mustGetElementById<HTMLButtonElement>("btnPrevIssue");
  const nextBtn = mustGetElementById<HTMLButtonElement>("btnNextIssue");
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  const w: any = window as any;
  w.__findingIdx = (w.__findingIdx ?? 0) + dir;
  if (w.__findingIdx < 0) w.__findingIdx = arr.length - 1;
  if (w.__findingIdx >= arr.length) w.__findingIdx = 0;
  const list = mustGetElementById<HTMLElement>("findingsList");
  const items = Array.from(list.querySelectorAll("li"));
  items.forEach((li, i) => {
    (li as HTMLElement).classList.toggle("active", i === w.__findingIdx);
  });
  const act = items[w.__findingIdx] as HTMLElement | undefined;
  if (act) act.scrollIntoView({ block: "nearest" });
  try { await highlightFinding(arr[w.__findingIdx]); } catch {}
}

function jumpToFinding(code: string) {
  const arr: AnnotationPlan[] = (window as any).__findings || [];
  if (!arr.length) return;
  const idx = arr.findIndex(o => o.rule_id === code || (o as any).code === code);
  if (idx < 0) return;
  (window as any).__findingIdx = idx;
  const list = mustGetElementById<HTMLElement>("findingsList");
  const items = Array.from(list.querySelectorAll("li"));
  items.forEach((li, i) => {
    (li as HTMLElement).classList.toggle("active", i === idx);
  });
  const act = items[idx] as HTMLElement | undefined;
  if (act) act.scrollIntoView({ block: "nearest" });
  try { highlightFinding(arr[idx]); } catch {}
}

async function onPrevIssue() { await navigateFinding(-1); }
async function onNextIssue() { await navigateFinding(1); }

export function renderAnalysisSummary(json: any) {
  clearHighlight().catch(() => {});
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
    mustGetElementById<HTMLElement>(id).textContent = val;
  };

  setText("clauseTypeOut", String(clauseType));
  setText("resFindingsCount", String(findings.length));
  setText("visibleHiddenOut", `${visible} / ${hidden}`);

  // Заполняем findings

  const findingsBlock = mustGetElementById('findingsBlock');
  const fCont = mustGetElementById<HTMLElement>("findingsList");
  fCont.innerHTML = "";
  visibleFindings.forEach((f, idx) => {
    const li = document.createElement("li");
    const title =
      f?.title || f?.finding?.title || f?.rule_id || "Issue";
    const snippet = f?.snippet || f?.evidence?.text || "";
    li.textContent = snippet ? `${title}: ${snippet}` : String(title);

    li.addEventListener('click', () => {
      const items = Array.from(fCont.querySelectorAll('li'));
      items.forEach((el, i) => {
        (el as HTMLElement).classList.toggle('active', i === idx);
      });
      (window as any).__findingIdx = idx;
      highlightFinding(f).catch(() => {});
    });

    const links = Array.isArray((f as any).links)
      ? (f as any).links.filter((l: any) => l?.type === 'conflict' && l?.targetFindingId)
      : [];
    if (links.length) {
      const div = document.createElement('div');
      div.textContent = `Conflicts: ${links.length} `;
      links.forEach((lnk: any, lidx: number) => {
        const a = document.createElement('a');
        a.href = '#';
        a.textContent = 'Jump to';
        a.addEventListener('click', ev => { ev.preventDefault(); jumpToFinding(lnk.targetFindingId); });
        div.appendChild(a);
        if (lidx < links.length - 1) div.append(' ');
      });
      li.appendChild(div);
    }

    fCont.appendChild(li);
  });
  findingsBlock.style.display = visibleFindings.length ? '' : 'none';

  // Заполняем рекомендации

  const recommendationsBlock = document.getElementById('recommendationsBlock') as HTMLElement | null;
  const recommendationsList = document.getElementById("recommendationsList") as HTMLElement | null;
  if (recommendationsList) {
    recommendationsList.innerHTML = "";
    for (const r of recs) {
      const li = document.createElement("li");
      li.textContent = r?.text || r?.advice || r?.message || "Recommendation";
      recommendationsList.appendChild(li);
    }
  }
  if (recommendationsBlock) {
    recommendationsBlock.style.display = recs.length ? '' : 'none';
  }

  // Показать блок результатов (если был скрыт стилями)
  const rb = mustGetElementById<HTMLElement>("resultsBlock");
  rb.style.removeProperty("display");
}

function renderResults(res: any) {
  const clause = slot("resClauseType", "clause-type");
  clause.textContent = res?.clause_type || "—";

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
  const findingsBlock = mustGetElementById('findingsBlock');
  findingsBlock.style.display = findingsArr.length ? '' : 'none';

  const recoArr = Array.isArray(res?.recommendations) ? res.recommendations : [];
  const recommendationsList = slot("recommendationsList", "recommendations") as HTMLElement | null;
  if (recommendationsList) {
    recommendationsList.innerHTML = "";
    recoArr.forEach((r: any) => {
      const li = document.createElement("li");
      li.textContent = typeof r === "string" ? r : JSON.stringify(r);
      recommendationsList.appendChild(li);
    });
  }
  const recommendationsBlock = mustGetElementById('recommendationsBlock');
  recommendationsBlock.style.display = recoArr.length ? '' : 'none';

  const count = slot("resFindingsCount", "findings-count");
  count.textContent = String(findingsArr.length);

  const pre = slot("rawJson", "raw-json");
  pre.textContent = JSON.stringify(res ?? {}, null, 2);
}

function mergeQaResults(json: any) {
  const existing: AnalyzeFinding[] = (window as any).__findings || [];
  const incoming = parseFindings(json);
  const merged = dedupeFindings([...existing, ...incoming]);
  return { ...(json || {}), findings: merged };
}

function wireResultsToggle() {
  const toggle = slot("toggleRaw", "toggle-raw-json");
  const pre = slot("rawJson", "raw-json");
  pre.style.display = "none";
  toggle.addEventListener("click", () => {
    pre.style.display = pre.style.display === "none" ? "block" : "none";
  });
}

function setConnBadge(ok: boolean | null) {
  const el = mustGetElementById<HTMLElement>("connBadge");
  el.textContent = `Conn: ${ok === null ? "—" : ok ? "✓" : "×"}`;
}

function setOfficeBadge(txt: string | null) {
  const el = mustGetElementById<HTMLElement>("officeBadge");
  el.textContent = `Office: ${txt ?? "—"}`;
}

async function onFixNumbering() {
  await Word.run(async ctx => {
    const styles = ["Heading 1", "Heading 2", "Heading 3"];
    for (let lvl = 0; lvl < styles.length; lvl++) {
      const paras = ctx.document.body.paragraphs.getByStyle(styles[lvl]);
      paras.load("items");
      await ctx.sync();
      for (const p of paras.items) {
        try {
          p.listFormat.removeNumbers();
          p.listFormat.applyNumberedDefault();
          if (p.listItem) p.listItem.level = lvl;
          const indent = 36 * (lvl + 1);
          p.paragraphFormat.leftIndent = indent;
          p.paragraphFormat.firstLineIndent = -36;
          p.paragraphFormat.lineSpacing = 240;
        } catch (e) {
          console.warn('fixNumbering', e);
        }
      }
    }
    await ctx.sync();
  }).catch((e: any) => logRichError(e, 'fixNumbering'));
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


export async function getClauseText(): Promise<string> {
  const src = $(Q.original);
  const direct = (src?.value || '').trim();
  if (direct) return direct;
  const text = await (globalThis as any).getSelectionText();
  if (text && src) {
    src.value = text;
    try { src.dispatchEvent(new Event('input', { bubbles: true })); } catch {}
  }
  return text.trim();
}

function getOriginalClauseOrSelection(): string {
  const src = $(Q.original) as HTMLTextAreaElement | null;
  return (src?.value || '').trim();
}

async function ensureClauseForDraftOrWarn(): Promise<string | null> {
  let clause = getOriginalClauseOrSelection();
  if (clause.length >= 20) return clause;
  try {
    clause = ((await (globalThis as any).getSelectionText()) || '').trim();
    if (clause.length >= 20) {
      const src = $(Q.original) as HTMLTextAreaElement | null;
      if (src) {
        src.value = clause;
        try { src.dispatchEvent(new Event('input', { bubbles: true })); } catch {}
      }
      return clause;
    }
  } catch {}
  notifyWarn('Please paste the original clause (min 20 chars) or select text in the document.');
  return null;
}

function detectContractType(): string {
  try { return (globalThis as any).detectContractType?.() || 'unknown'; }
  catch { return 'unknown'; }
}

function getVisibleFindingsForCurrentIssue(): any[] {
  try {
    const arr = (window as any).__findings || [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function getSelectionOffsetsSafe(): { start: number; end: number } | null {
  try { return (window as any).getSelectionOffsets?.() || null; }
  catch { return null; }
}

async function requestDraft(mode: 'friendly' | 'strict') {
  const clause = await ensureClauseForDraftOrWarn();
  if (!clause) return;

  const payload = {
    mode,
    clause_id: lastCid || undefined,
    text: clause,
    context: {
      law: 'UK',
      language: 'en-GB',
      contractType: detectContractType(),
    },
    findings: getVisibleFindingsForCurrentIssue().slice(0, 10),
    selection: getSelectionOffsetsSafe(),
  };

  let res: Response;
  try {
    res = await fetch('/api/gpt/draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': getApiKeyFromStore() || '',
        'X-Schema-Version': '1.4',
      },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    console.warn('Draft error', e);
    notifyWarn('Draft error');
    return;
  }

  if (!res.ok) {
    const t = await res.text();
    console.warn(`Draft failed: ${res.status} ${t}`);
    return;
  }

  const json = await res.json();
  const proposed = (json?.draft_text || '').toString();
  const dst = $(Q.proposed);
  const w: any = window as any;
  w.__last = w.__last || {};
  w.__last['gpt-draft'] = { json };
  if (dst) {
    if (!dst.id) dst.id = 'draftText';
    if (!dst.name) dst.name = 'proposed';
    (dst as any).dataset.role = 'proposed-text';
    dst.value = proposed;
    dst.dispatchEvent(new Event('input', { bubbles: true }));
    notifyOk('Draft ready');
    try { await insertDraftText(proposed, currentMode, json?.meta?.rationale); } catch {}
    onDraftReady(proposed);
  } else {
    notifyWarn('Proposed textarea not found');
    onDraftReady('');
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
  const hid = mustGetElementById<HTMLTextAreaElement>("originalText");
  if (hid !== src) {
    hid.value = text;
    try { hid.dispatchEvent(new Event("input", { bubbles: true })); } catch {}
  }
  (window as any).__lastAnalyzed = text;
  (window as any).toast?.("Whole doc loaded");
}

export async function onSuggestEdit(ev?: Event) {
  return withBusy(() => requestDraft(currentMode === 'friendly' ? 'friendly' : 'strict'));
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

export async function ensureTextForAnalysis(): Promise<string | null> {
  const orig = mustGetElementById<HTMLTextAreaElement>("originalText");
  let text = normalizeText(orig.value || "");
  if (!text) {
    const btn = mustGetElementById<HTMLButtonElement>("btnAnalyze");
    btn.disabled = true;
    try {
      text = normalizeText(await (globalThis as any).getWholeDocText());
      orig.value = text || "";
    } catch {
      text = "";
    } finally {
      btn.disabled = false;
    }
  }
  if (!text) {
    notifyWarn("Document is empty");
    return null;
  }
  (window as any).__lastAnalyzed = text;
  return text;
}

export async function onAnalyze() {
  if (analyzeInProgress) {
    console.log('[PANEL] analyze in progress - ignoring click');
    return;
  }
  for (const ctrl of pendingFetches) {
    if ((ctrl as any).__key === '/api/analyze') {
      console.log('[PANEL] pending /api/analyze fetch - ignoring click');
      return;
    }
  }
  analyzeInProgress = true;
  try {
    const base = await ensureTextForAnalysis();
    if (!base) return;
    await doAnalyze();
  } finally {
    analyzeInProgress = false;
  }
}

async function doAnalyze() {
  return withBusy(async () => {

    const btn = mustGetElementById<HTMLButtonElement>("btnAnalyze");
    const busy = mustGetElementById<HTMLElement>("busyBar");
    btn.disabled = true;
    busy.style.display = "";
    try {
      onDraftReady('');
      const base = (window as any).__lastAnalyzed as string | undefined;
      if (!base) { notifyErr("В документе нет текста"); return; }

      ensureHeaders();

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
        const ops = planAnnotations(filtered);
        (window as any).__findings = ops;
        (window as any).__findingIdx = 0;
        const list = mustGetElementById<HTMLElement>("findingsList");
        const frag = document.createDocumentFragment();
        ops.forEach((op, i) => {
          const li = document.createElement("li");
          li.textContent = `${op.rule_id}: ${op.raw}`;
          if (i === 0) li.classList.add("active");
          frag.appendChild(li);
        });
        list.innerHTML = "";
        list.appendChild(frag);
        if (isAddCommentsOnAnalyzeEnabled() && filtered.length) {
          await annotateFindingsIntoWord(filtered);
        }
      } catch (e) {
        console.warn("auto-annotate after analyze failed", e);
      }

        mustGetElementById<HTMLElement>("results")
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
      btn.disabled = false;
      busy.style.display = "none";
    }
  });
}

async function doQARecheck() {
  return withBusy(async () => {
    await clearHighlight();
    ensureHeaders();

    const docId = (window as any).__docId;
    const text = await getWholeDocText();
    (window as any).__lastAnalyzed = text;
    const payload: any = docId
      ? { document_id: docId, rules: {} }
      : { text, rules: {} };
    const { json } = await postJSON('/api/qa-recheck', payload);
      mustGetElementById<HTMLElement>("results").dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
    const ok = !json?.error;
    if (ok) {
      const prev: AnnotationPlan[] = (window as any).__findings || [];
      const prevIdx = (window as any).__findingIdx ?? 0;
      const key = (f: any) => f?.code || f?.rule_id || `${f?.rule_id}|${f?.raw || f?.snippet || ''}`;
      const prevKey = prev[prevIdx] ? key(prev[prevIdx]) : null;

      const parsed = parseFindings(json);
      const thr = getRiskThreshold();
      const filtered = filterByThreshold(parsed, thr);
      const ops = planAnnotations(filtered);
      const uniq = new Map<string, AnnotationPlan>();
      ops.forEach(op => {
        const k = key(op);
        if (k && !uniq.has(k)) uniq.set(k, op);
      });
      const deduped = Array.from(uniq.values());
      (window as any).__findings = deduped;

      let newIdx = 0;
      if (prevKey) {
        const found = deduped.findIndex(o => key(o) === prevKey);
        if (found >= 0) newIdx = found;
      }
      if (newIdx >= deduped.length) newIdx = 0;
      (window as any).__findingIdx = newIdx;

      const list = mustGetElementById<HTMLElement>("findingsList");
      const frag = document.createDocumentFragment();
      deduped.forEach((op, i) => {
        const li = document.createElement("li");
        li.textContent = `${op.rule_id}: ${op.raw}`;
        if (i === newIdx) li.classList.add("active");
        frag.appendChild(li);
      });
      list.innerHTML = "";
      list.appendChild(frag);

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
      const out = mustGetElementById<HTMLElement>('diffOutput');
      const cont = mustGetElementById<HTMLElement>('diffContainer');
      out.innerHTML = html || '';
      cont.style.display = html ? 'block' : 'none';
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

export async function onAcceptAll() {
  try {
    const dst = $(Q.proposed);
    const proposed = (dst?.value || "").trim();
    if (!proposed) { (window as any).toast?.("Nothing to accept"); return; }

    const cid = (mustGetElementById<HTMLElement>("cid").textContent || "").trim();
    const base = (() => {
      try { return (localStorage.getItem("backendUrl") || "https://127.0.0.1:9443").replace(/\/+$/, ""); }
      catch { return "https://127.0.0.1:9443"; }
    })();
    const link = cid && cid !== "—" ? `${base}/api/trace/${cid}` : "AI draft";

    await Word.run(async ctx => {
      const range = ctx.document.getSelection();
      (ctx.document as any).trackRevisions = true;
      range.insertText(proposed, Word.InsertLocation.replace);
      const res = await safeInsertComment(range, `${COMMENT_PREFIX} ${link}`);
      if (!res.ok) {
        await fallbackAnnotateWithContentControl(range, link);
      }

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
  if ((globalThis as any).__CAI_TESTING__) {
    console.log('[PANEL] wireUI skipped (__CAI_TESTING__)');
    return;
  }
  const missing = REQUIRED_IDS.filter(id => {
    try { mustGetElementById<HTMLElement>(id); return false; }
    catch { return true; }
  });
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

  const bookEl = mustGetElementById<HTMLElement>('loading-book');
    window.addEventListener('cai:busy', (e: any) => {
      const busy = !!(e?.detail?.busy);
      if (busy) bookEl.classList.remove('hidden');
      else bookEl.classList.add('hidden');
    });

    const s = logSupportMatrix();
    const disable = (id: string, reason?: string) => {
      const el = mustGetElementById<HTMLButtonElement>(id);
      el.disabled = true;
      el.title = reason ? `Not supported: ${reason}` : 'Not supported';
      if (reason) {
        try { console.log(`disabled ${id}: ${reason}`); } catch {}
      }
    };

    bindClick("#btnUseWholeDoc", onUseWholeDoc);
    const wholeBtn = mustGetElementById<HTMLButtonElement>('btnUseWholeDoc');
    wholeBtn.disabled = false;
  bindClick("#btnFixNumbering", onFixNumbering);
  if (ENV_MODE === 'dev') bindClick("#btnTest", doHealth);
    else {
      const bt = mustGetElementById<HTMLElement>('btnTest');
      bt.style.display = 'none';
    }
  bindClick("#btnQARecheck", doQARecheck);
    const draftBtn = mustGetElementById<HTMLButtonElement>('btnSuggestEdit');
    const origClause = $(Q.original);
    const syncDraftBtn = () => { draftBtn.disabled = !(origClause && origClause.value.trim()); };
    origClause?.addEventListener('input', syncDraftBtn);
  try {
    Office.context.document.addHandlerAsync?.(Office.EventType.DocumentSelectionChanged, async () => {
      try {
        const txt = await (globalThis as any).getSelectionText();
        if (txt && origClause) {
          origClause.value = txt;
          try { origClause.dispatchEvent(new Event('input', { bubbles: true })); } catch {}
        }
      } catch {}
    });
  } catch {}
    syncDraftBtn();
    draftBtn.addEventListener('click', onSuggestEdit);
  bindClick("#btnApplyTracked", onApplyTracked);
  bindClick("#btnAcceptAll", onAcceptAll);
  bindClick("#btnRejectAll", onRejectAll);
  bindClick("#btnPrevIssue", onPrevIssue);
  bindClick("#btnNextIssue", onNextIssue);
  bindClick("#btnPreviewDiff", onPreviewDiff);
  bindClick("#btnClearAnnots", clearAnnotations);
  bindClick("#btnSave", onSaveBackend);
    const cb = (() => {
      try { return mustGetElementById<HTMLInputElement>("cai-comment-on-analyze"); }
      catch { return mustGetElementById<HTMLInputElement>("chkAddCommentsOnAnalyze"); }
    })();
    cb.checked = isAddCommentsOnAnalyzeEnabled();
    cb.addEventListener("change", () => setAddCommentsOnAnalyze(!!cb.checked));
    const annotateBtn = mustGetElementById<HTMLButtonElement>("btnAnnotate");
    annotateBtn.addEventListener("click", async () => {
      if (annotateBtn.disabled) return;
      annotateBtn.disabled = true;
      try {
        const data = (window as any).__last?.analyze?.json || {};
        const findings = (globalThis as any).parseFindings(data);
        try {
          await (globalThis as any).annotateFindingsIntoWord(findings);
        } catch (e: any) {
          const code = e?.code || e?.name || '';
          if (code === 'SearchStringInvalidOrTooLong' || code === 'InvalidOrTooLong' || code === 'InvalidArgument') {
            (globalThis as any).toast2?.('Search failed (long text), skipping some anchors', 'warn');
            console.warn('[annotate run] search error', code);
          } else {
            console.warn('[annotate run] error', e);
          }
        }
      } finally {
        annotateBtn.disabled = false;
      }
    });
    annotateBtn.classList.remove("js-disable-while-busy");
    annotateBtn.removeAttribute("disabled");

  mustGetElementById<HTMLElement>('results').addEventListener('ca.qa', (ev: any) => {
    const json = ev?.detail;
    try {
      if (!json || json.error) {
        renderResults(json || {});
        renderAnalysisSummary(json || {});
        return;
      }
      const merged = mergeQaResults(json);
      renderResults(merged);
      renderAnalysisSummary(merged);
    } catch (e) {
      console.warn('ca.qa handler failed', e);
      renderResults(json || {});
      renderAnalysisSummary(json || {});
    }
  });

  onDraftReady('');
  wireResultsToggle();

  console.log("Panel UI wired [OK]");
  const ab = mustGetElementById<HTMLButtonElement>("btnAnalyze");
  ab.disabled = true;
  ensureHeaders();
  updateStatusChip();
  updateAnchorBadge();

  if (!s.revisions) { disable('btnApplyTracked', 'revisions'); disable('btnAcceptAll', 'revisions'); disable('btnRejectAll', 'revisions'); }
  if (!s.comments) {
    disable('btnAnnotate', 'comments');
    disable('btnAcceptAll', s.commentsReason);
    notifyWarn('Comments API not available in this Word build');
  }
  if (!s.search) { disable('btnPrevIssue', 'search'); disable('btnNextIssue', 'search'); disable('btnQARecheck', 'search'); }
  if (!s.contentControls) { disable('btnAnnotate', 'contentControls'); }
  if (!s.revisions || !s.comments || !s.search || !s.contentControls) {
    try { setOfficeBadge('Word ⚠'); } catch {}
  }
}

g.wireUI = g.wireUI || wireUI;

// self-test moved to startup.selftest.ts

  function onDraftReady(text: string) {
    const show = !!text.trim();
    const apply = mustGetElementById<HTMLButtonElement>('btnApplyTracked');
    const accept = mustGetElementById<HTMLButtonElement>('btnAcceptAll');
    const reject = mustGetElementById<HTMLButtonElement>('btnRejectAll');
    const diff = mustGetElementById<HTMLButtonElement>('btnPreviewDiff');
    const pane = mustGetElementById<HTMLElement>('draftPane');
    const dst = mustGetElementById<HTMLTextAreaElement>('draftText');
    dst.value = text;
    pane.style.display = show ? '' : 'none';
    apply.disabled = !show;
    accept.disabled = !show;
    reject.disabled = !show;
    diff.disabled = !show;
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

let domReady = false;
let officeReady = false;
let officeInfo: Office.OfficeInfo | undefined;
let bootstrapped = false;
let bootstrapCalls = 0;

function tryBootstrap() {
  if (bootstrapped) {
    console.log(`bootstrap invoked x${bootstrapCalls+1}`);
    return;
  }
  if (!(domReady && officeReady)) return;
  bootstrapped = true;
  bootstrapCalls++;
  console.log('bootstrap invoked x1');
  void bootstrap(officeInfo);
}

export function invokeBootstrap(info?: Office.OfficeInfo) {
  officeInfo = info;
  domReady = true;
  officeReady = true;
  tryBootstrap();
}
export function getBootstrapCount() { return bootstrapCalls; }

if (!(globalThis as any).__CAI_TESTING__) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      domReady = true;
      tryBootstrap();
    });
  } else {
    domReady = true;
    tryBootstrap();
  }
  Office.onReady(info => {
    officeReady = true;
    officeInfo = info;
    tryBootstrap();
  });
}
