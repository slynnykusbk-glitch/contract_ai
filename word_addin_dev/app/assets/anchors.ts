import { normalizeIntakeText } from "./normalize_intake.ts";
import { safeBodySearch } from "./safeBodySearch.ts";

export function normalizeSnippetForSearch(snippet: string | null | undefined): string {
  if (!snippet) return "";
  return normalizeIntakeText(String(snippet));
}

export function pickLongToken(snippet: string | null | undefined): string | null {
  if (!snippet) return null;
  const normalized = normalizeIntakeText(String(snippet));
  const tokens = normalized
    .replace(/[^\p{L}\p{N} ]/gu, " ")
    .split(" ")
    .map(t => t.trim())
    .filter(Boolean);
  if (!tokens.length) return null;
  const sorted = tokens.sort((a, b) => b.length - a.length);
  const longest = sorted.find(t => t.length >= 8) || sorted[0];
  return longest ? longest.slice(0, 64) : null;
}

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

  const raw = snippetRaw || "";
  const rawRes = await attempt(raw);
  let items: RangeLike[] = rawRes?.items || [];

  if (!items.length) {
    const norm = normalizeIntakeText(raw).trim();
    if (norm) {
      const normRes = await attempt(norm);
      items = normRes?.items || [];
    }
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

export async function searchNth(body: BodyLike, snippetRaw: string, nth: number, opt?: Word.SearchOptions): Promise<RangeLike | null> {
  if (!body || !snippetRaw) return null;
  const idx = typeof nth === 'number' && Number.isFinite(nth) && nth >= 0 ? Math.floor(nth) : 0;
  const searchOpts = opt || { matchCase: false, matchWholeWord: false };
  const res = await safeBodySearch(body, snippetRaw, searchOpts);
  let items: RangeLike[] = res?.items || [];
  if (!items.length) {
    const norm = normalizeIntakeText(snippetRaw).trim();
    if (norm && norm !== snippetRaw) {
      const normRes = await safeBodySearch(body, norm, searchOpts);
      items = normRes?.items || [];
    }
  }
  if (!items.length) return null;
  if (idx >= items.length) return null;
  const picked = items[idx] ?? null;
  if (!picked) return null;
  try {
    body.context?.trackedObjects?.add?.(picked);
  } catch {}
  return picked;
}
