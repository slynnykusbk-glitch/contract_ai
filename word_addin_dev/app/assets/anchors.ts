import { normalizeTextFull } from "./normalize_full.ts";
import { normalizeIntakeText } from "./normalize_intake.ts";
import { safeBodySearch } from "./safeBodySearch.ts";

export function normalizeSnippetForSearch(snippet: string | null | undefined): string {
  if (!snippet) return "";
  return normalizeTextFull(String(snippet)).text;
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

export type AnchorMethod = 'offset' | 'nth' | 'normalized' | 'token';

type OffsetCandidate = { start: number; end?: number | null | undefined };

export interface AnchorByOffsetsOptions {
  body: BodyLike;
  snippet: string;
  start?: number | null;
  end?: number | null;
  nth?: number | null;
  searchOptions?: Word.SearchOptions;
  normalizedCandidates?: Array<string | OffsetCandidate | null | undefined>;
  token?: string | null;
  onMethod?: (method: AnchorMethod) => void;
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

function pushNormalizedVariant(target: Set<string>, cand: string | null | undefined, skip?: string): void {
  if (!cand) return;
  const normalized = normalizeSnippetForSearch(cand);
  if (!normalized) return;
  if (skip && normalized === skip) return;
  target.add(normalized);
}

function trackRange(body: BodyLike, range: RangeLike | null | undefined): void {
  if (!range) return;
  try {
    body.context?.trackedObjects?.add?.(range);
  } catch {}
}

function isOffsetCandidate(value: unknown): value is OffsetCandidate {
  return !!value && typeof value === 'object' && typeof (value as any).start === 'number';
}

export async function anchorByOffsets(opts: AnchorByOffsetsOptions): Promise<RangeLike | null> {
  if (!opts?.body || !opts.snippet) return null;
  const { body, snippet } = opts;
  const searchOptions = opts.searchOptions || { matchCase: false, matchWholeWord: false };
  const nth = typeof opts.nth === 'number' && Number.isFinite(opts.nth) && opts.nth >= 0 ? Math.floor(opts.nth) : 0;
  const logMethod = (method: AnchorMethod) => {
    try {
      opts.onMethod?.(method);
    } catch {}
  };

  const g: any = globalThis as any;
  const allowOffsets = g?.__cfg_anchorOffsets !== 0;
  const snippetNormalized = normalizeSnippetForSearch(snippet);
  const textCandidates: string[] = [];
  const offsetGuesses: { start: number; end?: number | null }[] = [];
  const seenOffsets = new Set<string>();

  const addOffsetGuess = (startValue: number | null | undefined, endValue: number | null | undefined) => {
    if (typeof startValue !== 'number' || !Number.isFinite(startValue) || startValue < 0) return;
    const start = Math.floor(startValue);
    let end: number | null = null;
    if (typeof endValue === 'number' && Number.isFinite(endValue) && endValue > startValue) {
      end = Math.floor(endValue);
    }
    const key = `${start}:${end ?? ''}`;
    if (seenOffsets.has(key)) return;
    seenOffsets.add(key);
    offsetGuesses.push({ start, end });
  };

  if (allowOffsets && typeof opts.start === 'number' && Number.isFinite(opts.start) && opts.start >= 0) {
    addOffsetGuess(opts.start, opts.end ?? null);
  }

  for (const cand of opts.normalizedCandidates || []) {
    if (isOffsetCandidate(cand)) {
      if (allowOffsets) addOffsetGuess(cand.start, cand.end ?? null);
    } else if (typeof cand === 'string') {
      textCandidates.push(cand);
    }
  }

  const tryOffset = async (expectedStart: number, expectedEndHint: number | null | undefined) => {
    const expectedEnd =
      typeof expectedEndHint === 'number' && Number.isFinite(expectedEndHint) && expectedEndHint > expectedStart
        ? Math.floor(expectedEndHint)
        : expectedStart + snippetNormalized.length;
    const expectedLength = Math.max(1, expectedEnd - expectedStart);

    const needles = new Set<string>();
    if (snippet) needles.add(snippet);
    if (snippetNormalized && snippetNormalized !== snippet) needles.add(snippetNormalized);
    for (const cand of textCandidates) {
      pushNormalizedVariant(needles, cand, snippetNormalized);
    }

    let bestRange: RangeLike | null = null;
    let bestDelta = Number.POSITIVE_INFINITY;

    for (const needle of needles) {
      if (!needle) continue;
      const res = await safeBodySearch(body as any, needle, searchOptions);
      const items: RangeLike[] = res?.items || [];
      for (const item of items) {
        const start = typeof item.start === 'number' ? item.start : 0;
        const delta = Math.abs(start - expectedStart);
        if (delta < bestDelta) {
          bestDelta = delta;
          bestRange = item;
          if (delta === 0) break;
        }
      }
      if (bestDelta === 0) break;
    }

    if (bestRange && bestDelta <= Math.max(5, expectedLength)) {
      trackRange(body, bestRange);
      logMethod('offset');
      return bestRange;
    }
    return null;
  };

  if (allowOffsets) {
    for (const guess of offsetGuesses) {
      const range = await tryOffset(guess.start, guess.end ?? null);
      if (range) {
        return range;
      }
    }
  }

  let range = await searchNth(body, snippet, nth, searchOptions);
  if (range) {
    logMethod('nth');
    return range;
  }

  const variants = new Set<string>();
  if (snippetNormalized) variants.add(snippetNormalized);
  for (const cand of textCandidates) {
    pushNormalizedVariant(variants, cand, snippetNormalized);
  }

  for (const variant of variants) {
    range = await searchNth(body, variant, nth, searchOptions);
    if (range) {
      logMethod('normalized');
      return range;
    }
  }

  const token = opts.token ?? pickLongToken(snippet);
  if (token) {
    const tokenRange = await searchNth(body, token, 0, searchOptions);
    if (tokenRange) {
      logMethod('token');
      return tokenRange;
    }
  }

  return null;
}
