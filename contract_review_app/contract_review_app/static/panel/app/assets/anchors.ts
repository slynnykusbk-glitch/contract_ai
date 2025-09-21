import { normalizeText } from "./dedupe.ts";
import { safeBodySearch } from "./safeBodySearch.ts";

interface RangeLike {
  start?: number;
  end?: number;
  [key: string]: any;
}

interface BodyLike {
  context: any;
  search: (txt: string, opts: any) => any;
}

/**
 * Find non-overlapping anchors in the document body for a raw snippet.
 *
 * Searches for the raw snippet first. If no matches are found, falls back to
 * searching the normalized snippet (same rules as backend normalization).
 * Returned ranges are sorted by (start,end) and overlapping ranges are pruned,
 * keeping the longest (or first if equal). All returned ranges are added to
 * ``context.trackedObjects``.
 */
export async function findAnchors(body: BodyLike, snippetRaw: string, opts?: { nth?: number | null }): Promise<RangeLike[]> {
  const ctx = body.context;
  const opt = { matchCase: false, matchWholeWord: false };

  const attempt = async (txt: string) => await safeBodySearch(body, txt, opt);

  const rawRes = await attempt(snippetRaw || "");
  let items: RangeLike[] = rawRes?.items || [];

  if (!items.length) {
    const norm = normalizeText(snippetRaw || "");
    const normRes = await attempt(norm);
    items = normRes?.items || [];
  }

  // Sort by start,end
  items.sort((a, b) => {
    const sa = a.start ?? 0;
    const sb = b.start ?? 0;
    if (sa !== sb) return sa - sb;
    const ea = a.end ?? sa;
    const eb = b.end ?? sb;
    return ea - eb;
  });

  // Merge overlaps keeping longest/first
  const result: RangeLike[] = [];
  for (const r of items) {
    const start = r.start ?? 0;
    const end = r.end ?? start;
    const last = result[result.length - 1];
    if (last && start < (last.end ?? start)) {
      const lastLen = (last.end ?? 0) - (last.start ?? 0);
      const curLen = end - start;
      if (curLen > lastLen) {
        result[result.length - 1] = r;
      }
      continue;
    }
    result.push(r);
  }

  const nth = opts?.nth;
  if (typeof nth === 'number' && Number.isFinite(nth) && nth >= 0 && result.length) {
    const idx = Math.min(Math.floor(nth), result.length - 1);
    const preferred = result[idx];
    if (preferred) {
      const reordered = [preferred, ...result.slice(0, idx), ...result.slice(idx + 1)];
      result.length = 0;
      result.push(...reordered);
    }
  }

  for (const r of result) {
    try {
      ctx.trackedObjects?.add?.(r);
    } catch {
      // ignore tracking errors
    }
  }

  return result;
}

export type { RangeLike };
