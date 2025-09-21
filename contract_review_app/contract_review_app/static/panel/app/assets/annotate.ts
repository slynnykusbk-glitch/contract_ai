import { AnalyzeFinding } from "./api-client.ts";
import { dedupeFindings, normalizeText } from "./dedupe.ts";
import { safeBodySearch } from "./safeBodySearch.ts";
import type { AnalyzeFindingEx, AnnotationPlanEx } from "./types.ts";

/** Utilities for inserting comments into Word with batching and retries. */
export interface CommentItem {
  range: any;
  message: string;
}

export async function safeInsertComment(range: Word.Range, text: string): Promise<{ ok: boolean; err?: any }> {
  const context: any = (range as any).context;
  let lastErr: any = null;
  try {
    const anyDoc = (context?.document as any);
    if (anyDoc?.comments?.add) {
      anyDoc.comments.add(range, text);
      await context?.sync?.();
      return { ok: true };
    }
  } catch (e) { lastErr = e; }
  try {
    range.insertComment(text);
    await context?.sync?.();
    return { ok: true };
  } catch (e) { lastErr = e; }
  try {
    await context?.sync?.();
    const anyDoc = (context?.document as any);
    if (anyDoc?.comments?.add) {
      anyDoc.comments.add(range, text);
      await context?.sync?.();
      return { ok: true };
    }
  } catch (e) { lastErr = e; }
  const g: any = globalThis as any;
  console.warn("safeInsertComment failed", lastErr);
  g.logRichError?.(lastErr, "insertComment");
  g.notifyWarn?.("Failed to insert comment");
  return { ok: false, err: lastErr };
}

export async function fallbackAnnotateWithContentControl(range: Word.Range, text: string): Promise<{ ok: boolean }> {
  const ctx: any = (range as any).context;
  try {
    range.load?.("parentContentControl");
    await ctx?.sync?.();
  } catch {}
  try {
    const parent: any = (range as any).parentContentControl;
    if (parent && parent.tag === "cai-note") {
      return { ok: false };
    }
  } catch {}
  try {
    const cc: any = range.insertContentControl();
    cc.tag = "cai-note";
    cc.title = "ContractAI Note";
    try { cc.color = "yellow" as any; } catch {}
    cc.insertText(`CAI: ${text}`, Word.InsertLocation.end);
    await ctx?.sync?.();
    return { ok: true };
  } catch (e) {
    console.warn("fallbackAnnotateWithContentControl failed", e);
    return { ok: false };

  }
}

/**
 * Insert comments for provided ranges. Operations are batched: ``context.sync``
 * is called after every 20 successful insertions and once at the end. If
 * ``range.insertComment`` throws an error containing ``0xA7210002`` it retries
 * once after rehydrating the range via ``expandTo(context.document.body)``. On
 * second failure the error is logged and the comment is skipped.
 *
 * Returns the number of comments successfully queued for insertion.
 */
export async function insertComments(ctx: any, items: CommentItem[]): Promise<number> {
  let inserted = 0;
  for (const it of items) {
    let r = it.range;
    const msg = it.message;
    let res = await safeInsertComment(r, msg);
    if (!res.ok && res.err && String(res.err).includes("0xA7210002")) {
      try {
        r = r.expandTo ? r.expandTo(ctx.document.body) : r;
        res = await safeInsertComment(r, msg);
      } catch (e2) {
        res = { ok: false, err: e2 };
        console.warn("annotate retry failed", e2);

      }
    }
    if (res.ok) {
      inserted++;
    } else {
      const fb = await fallbackAnnotateWithContentControl(r, msg.replace(COMMENT_PREFIX, "").trim());
      if (fb.ok) inserted++;
    }
  }
  return inserted;
}

function nthOccurrenceIndex(hay: string, needle: string, startPos?: number): number {
  if (!hay || !needle) return 0;
  let idx = -1, n = 0;
  while ((idx = hay.indexOf(needle, idx + 1)) !== -1 && idx < (startPos ?? hay.length)) n++;
  return n;
}

const normalizedCache = new Map<string, string>();

function normalizeCached(text: string): string {
  let cached = normalizedCache.get(text);
  if (cached == null) {
    cached = normalizeText(text);
    normalizedCache.set(text, cached);
  }
  return cached;
}

export function computeNthFromOffsets(text: string, snippet: string, start?: number): number | null {
  if (!text || !snippet) return null;
  if (typeof start !== 'number' || !Number.isFinite(start) || start < 0) return null;
  const normSnippet = normalizeText(snippet);
  if (!normSnippet) return null;

  const normText = normalizeCached(text);
  const prefix = text.slice(0, Math.max(0, Math.min(text.length, Math.floor(start))));
  const normPrefix = normalizeText(prefix);

  if (!normText) return null;

  let count = 0;
  let searchIdx = 0;
  while (true) {
    const foundIdx = normText.indexOf(normSnippet, searchIdx);
    if (foundIdx === -1 || foundIdx >= normPrefix.length) break;
    count++;
    searchIdx = foundIdx + Math.max(normSnippet.length, 1);
  }
  return count;
}

function isDryRunAnnotateEnabled(): boolean {
  try {
    return !!(document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null)?.checked;
  } catch {
    return false;
  }
}

export const COMMENT_PREFIX = "[CAI]";

function buildLegalComment(f: AnalyzeFinding): string {
  if (!f.rule_id || !f.snippet) {
    console.warn("buildLegalComment: missing required fields", f);
    return "";
  }
  const parts = [f.rule_id];
  if (f.advice) parts.push(f.advice);
  if (f.law_refs?.length) parts.push(f.law_refs.join("; "));
  return `${COMMENT_PREFIX} ${parts.join("\n")}`;
}

export interface AnnotationPlan extends AnnotationPlanEx {
  raw: string;
  norm: string;
  occIdx: number;
  msg: string;
  rule_id: string;
  normalized_fallback: string;
}

export const MAX_ANNOTATE_OPS = 200;

/**
 * Prepare annotate operations from analysis findings without touching Word objects.
 */
export function planAnnotations(findings: AnalyzeFindingEx[]): AnnotationPlan[] {
  const baseText = String((globalThis as any).__lastAnalyzed || "");
  const baseNorm = normalizeText(baseText);
  const list = Array.isArray(findings) ? findings : [];
  const deduped = dedupeFindings(list as AnalyzeFinding[]);
  const sorted = deduped
    .slice()
    .sort((a, b) => (a.start ?? Number.POSITIVE_INFINITY) - (b.start ?? Number.POSITIVE_INFINITY));


  const ops: AnnotationPlan[] = [];
  let lastEnd = -1;

  let skipped = 0;
  for (const f of sorted) {
    if (!f || !f.rule_id || !f.snippet || typeof f.start !== "number") {
      skipped++;
      continue;
    }
    const snippet = f.snippet;
    const start = f.start;
    const end = typeof f.end === "number" ? f.end : start + snippet.length;
    if (start < lastEnd) {
      skipped++;
      continue;
    }
    const norm = normalizeText(snippet);
    const nth = computeNthFromOffsets(baseText, snippet, start);
    const occIdx = typeof nth === "number" ? nth : nthOccurrenceIndex(baseNorm, norm, start);
    ops.push({
      raw: snippet,
      norm,
      occIdx,
      msg: buildLegalComment(f),
      rule_id: f.rule_id,
      normalized_fallback: normalizeText((f as any).normalized_snippet || ""),
      start,
      end,
      nth: nth ?? undefined
    });

    lastEnd = end;
    if (ops.length >= MAX_ANNOTATE_OPS) break;
  }
  const g: any = globalThis as any;
  if (skipped) g.notifyWarn?.(`Skipped ${skipped} overlaps/invalid`);
  if (deduped.length > MAX_ANNOTATE_OPS) g.notifyWarn?.(`Truncated to first ${MAX_ANNOTATE_OPS} findings`);
  g.notifyOk?.(`Will insert: ${ops.length}`);
  return ops;
}

/**
 * Convert findings directly into Word comments using a two-phase plan.
 */
export async function findingsToWord(findings: AnalyzeFindingEx[]): Promise<number> {
  const ops = planAnnotations(findings);
  if (!ops.length) return 0;
  const g: any = globalThis as any;
  return await g.Word?.run?.(async (ctx: any) => {
    const body = ctx.document.body;
    const searchOpts = { matchCase: false, matchWholeWord: false } as Word.SearchOptions;
    const used: { start: number; end: number }[] = [];
    let inserted = 0;

    const pick = (coll: any, occ: number) => {
      const arr = coll?.items || [];
      if (!arr.length) return null;
      return arr[Math.min(Math.max(occ, 0), arr.length - 1)] || null;
    };

    for (const op of ops) {
      const desired = typeof op.nth === "number" ? op.nth : op.occIdx;
      let target: any = null;

      const sRaw = await safeBodySearch(body, op.raw, searchOpts);
      target = pick(sRaw, desired);

      if (!target) {
        const fb = op.normalized_fallback && op.normalized_fallback !== op.norm ? op.normalized_fallback : op.norm;
        if (fb && fb.trim()) {
          const sNorm = await safeBodySearch(body, fb, searchOpts);
          target = pick(sNorm, desired);
        }
      }

      if (!target) {
        const token = (() => {
          const tks = op.raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter(x => x.length >= 12);
          if (tks.length) return tks.sort((a, b) => b.length - a.length)[0].slice(0, 64);
          return null;
        })();
        if (token) {
          const sTok = await safeBodySearch(body, token, searchOpts);
          target = pick(sTok, 0);
        }
      }

      if (target) {
        target.load(["start", "end"]);
        await ctx.sync();
        const start = target.start ?? 0;
        const end = target.end ?? start;
        if (used.some(r => Math.max(r.start, start) < Math.min(r.end, end))) {
          console.warn("[annotate] overlapping range", { rid: op.rule_id, start, end });
          continue;
        }
        let ok = false;
        if (isDryRunAnnotateEnabled()) {
          try { target.select(); ok = true; } catch {}
        } else if (op.msg) {
          const res = await safeInsertComment(target, op.msg);
          if (res.ok) ok = true;
          else {
            const fb = await fallbackAnnotateWithContentControl(target, op.msg.replace(COMMENT_PREFIX, "").trim());
            ok = fb.ok;
          }
        }
        if (ok) {
          used.push({ start, end });
          inserted++;

        }
      } else {
        console.warn("[annotate] no match for snippet", { rid: op.rule_id, snippet: op.raw.slice(0, 120) });
      }
    }

    await ctx.sync();
    return inserted;
  }).catch((e: any) => {
    const gg: any = globalThis as any;
    gg.logRichError?.(e, "annotate");
    console.warn("annotate run fail", e?.code, e?.message, e?.debugInfo);
    return 0;
  });
}
