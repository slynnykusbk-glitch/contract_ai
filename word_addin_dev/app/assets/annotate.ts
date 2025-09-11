import { AnalyzeFinding } from "./api-client";
import { dedupeFindings, normalizeText } from "./dedupe";

/** Utilities for inserting comments into Word with batching and retries. */
export interface CommentItem {
  range: any;
  message: string;
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
  let pending = 0;
  for (const it of items) {
    let r = it.range;
    const msg = it.message;
    try {
      r.insertComment(msg);
      inserted++;
    } catch (e: any) {
      if (String(e).includes("0xA7210002")) {
        try {
          r = r.expandTo ? r.expandTo(ctx.document.body) : r;
          r.insertComment(msg);
          inserted++;
        } catch (e2) {
          console.warn("annotate retry failed", e2);
        }
      } else {
        console.warn("annotate error", e);
      }
    }
    pending++;
    if (pending % 20 === 0) {
      await ctx.sync();
    }
  }
  if (pending % 20 !== 0) {
    await ctx.sync();
  }
  return inserted;
}

function nthOccurrenceIndex(hay: string, needle: string, startPos?: number): number {
  if (!hay || !needle) return 0;
  let idx = -1, n = 0;
  while ((idx = hay.indexOf(needle, idx + 1)) !== -1 && idx < (startPos ?? hay.length)) n++;
  return n;
}

function isDryRunAnnotateEnabled(): boolean {
  try {
    return !!(document.getElementById("cai-dry-run-annotate") as HTMLInputElement | null)?.checked;
  } catch {
    return false;
  }
}

function buildLegalComment(f: AnalyzeFinding): string {
  if (!f.rule_id || !f.snippet) {
    console.warn("buildLegalComment: missing required fields", f);
    return "";
  }
  const parts = [f.rule_id];
  if (f.advice) parts.push(f.advice);
  if (f.law_refs?.length) parts.push(f.law_refs.join("; "));
  return parts.join("\n");
}

export interface AnnotateOp {
  raw: string;
  norm: string;
  occIdx: number;
  msg: string;
  rule_id: string;
  normalized_fallback: string;
}

/**
 * Prepare annotate operations from analysis findings without touching Word objects.
 */
export function annotate(findings: AnalyzeFinding[]): AnnotateOp[] {
  const base = normalizeText((globalThis as any).__lastAnalyzed || "");
  const deduped = dedupeFindings(findings || []);
  const sorted = deduped.slice().sort((a, b) => (b.end ?? 0) - (a.end ?? 0));

  const ops: AnnotateOp[] = [];
  let lastStart = Number.POSITIVE_INFINITY;
  let skipped = 0;
  for (const f of sorted) {
    if (!f || !f.rule_id || !f.snippet) { skipped++; continue; }
    const snippet = f.snippet;
    const end = typeof f.end === "number" ? f.end : (typeof f.start === "number" ? f.start + snippet.length : undefined);
    if (typeof end === "number" && end > lastStart) { skipped++; continue; }
    const norm = normalizeText(snippet);
    const occIdx = nthOccurrenceIndex(base, norm, f.start);
    ops.push({
      raw: snippet,
      norm,
      occIdx,
      msg: buildLegalComment(f),
      rule_id: f.rule_id,
      normalized_fallback: normalizeText((f as any).normalized_snippet || "")
    });
    if (typeof f.start === "number") lastStart = f.start;
  }
  const g: any = globalThis as any;
  if (skipped) g.notifyWarn?.(`Skipped ${skipped} overlaps/invalid`);
  g.notifyOk?.(`Will insert: ${ops.length}`);
  return ops;
}

/**
 * Convert findings directly into Word comments using a two-phase plan.
 */
export async function findingsToWord(findings: AnalyzeFinding[]): Promise<number> {
  const ops = annotate(findings);
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
      let target: any = null;

      const sRaw = body.search(op.raw, searchOpts);
      sRaw.load("items");
      await ctx.sync();
      target = pick(sRaw, op.occIdx);

      if (!target) {
        const fb = op.normalized_fallback && op.normalized_fallback !== op.norm ? op.normalized_fallback : op.norm;
        if (fb && fb.trim()) {
          const sNorm = body.search(fb, searchOpts);
          sNorm.load("items");
          await ctx.sync();
          target = pick(sNorm, op.occIdx);
        }
      }

      if (!target) {
        const token = (() => {
          const tks = op.raw.replace(/[^\p{L}\p{N} ]/gu, " ").split(" ").filter(x => x.length >= 12);
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
        target.load(["start", "end"]);
        await ctx.sync();
        const start = target.start ?? 0;
        const end = target.end ?? start;
        if (used.some(r => Math.max(r.start, start) < Math.min(r.end, end))) {
          continue; // conflict
        }
        if (isDryRunAnnotateEnabled()) {
          try { target.select(); } catch {}
        } else if (op.msg) {
          target.insertComment(op.msg);
        }
        used.push({ start, end });
        inserted++;
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

