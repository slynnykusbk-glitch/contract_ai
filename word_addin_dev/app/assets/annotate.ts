import { AnalyzeFinding } from "./api-client.ts";
import { dedupeFindings, normalizeText } from "./dedupe.ts";
import { findAnchors } from "./anchors.ts";

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

export const COMMENT_PREFIX = "AI edit:";

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

export interface AnnotationPlan {
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
export function planAnnotations(findings: AnalyzeFinding[]): AnnotationPlan[] {
  const base = normalizeText((globalThis as any).__lastAnalyzed || "");
  const list = Array.isArray(findings) ? findings : [];
  const deduped = dedupeFindings(list);
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
    const occIdx = nthOccurrenceIndex(base, norm, start);
    ops.push({
      raw: snippet,
      norm,
      occIdx,
      msg: buildLegalComment(f),
      rule_id: f.rule_id,
      normalized_fallback: normalizeText((f as any).normalized_snippet || "")
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
 * Insert comments for provided findings. Builds an annotation plan and anchors
 * each snippet to Word ranges using ``findAnchors``.
 */
export async function annotateFindingsIntoWord(findings: AnalyzeFinding[]): Promise<number> {
  const ops = planAnnotations(findings);
  if (!ops.length) return 0;
  const g: any = globalThis as any;
  return await g.Word?.run?.(async (ctx: any) => {
    const body = ctx.document.body as any;
    const used: { start: number; end: number }[] = [];
    let inserted = 0;
    for (const op of ops) {
      let anchors = await findAnchors(body, op.raw);
      let target: any = anchors[Math.min(op.occIdx, anchors.length - 1)] || null;
      if (!target && op.normalized_fallback && op.normalized_fallback !== op.norm) {
        anchors = await findAnchors(body, op.normalized_fallback);
        target = anchors[Math.min(op.occIdx, anchors.length - 1)] || null;
      }
      if (target) {
        target.load?.(["start", "end"]);
        await ctx.sync();
        const start = target.start ?? 0;
        const end = target.end ?? start;
        if (used.some(r => Math.max(r.start, start) < Math.min(r.end, end))) {
          console.warn("[annotate] overlapping range", { rid: op.rule_id, start, end });
          continue;
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
      await ctx.sync();
    }
    return inserted;
  }).catch((e: any) => {
    const gg: any = globalThis as any;
    gg.logRichError?.(e, "annotate");
    console.warn("annotate run fail", e?.code, e?.message, e?.debugInfo);
    return 0;
  });
}


