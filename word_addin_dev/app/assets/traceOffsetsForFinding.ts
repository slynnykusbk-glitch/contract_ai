import type { AnalyzeFindingEx } from "./types.ts";

export interface OffsetSpan {
  start: number;
  end: number;
}

type TraceCandidate = {
  rule_id?: string | null;
  reasons?: Array<{ offsets?: Array<OffsetLike> | null } | null> | null;
};

type TraceSegment = {
  segment_id?: number | string | null;
  candidates?: Array<TraceCandidate | null> | null;
};

type OffsetLike = OffsetSpan | [number, number] | { start?: number | null; end?: number | null } | null | undefined;

type TraceBody = {
  dispatch?: {
    segments?: Array<TraceSegment | null> | null;
    candidates?: Array<TraceCandidate | null> | null;
  } | null;
};

function toInt(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.floor(value);
  }
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function extractOffsets(entries: OffsetLike[]): OffsetSpan[] {
  const spans: OffsetSpan[] = [];
  for (const entry of entries) {
    if (!entry) continue;
    let start: number | undefined;
    let end: number | undefined;
    if (Array.isArray(entry) && entry.length >= 2) {
      start = toInt(entry[0]);
      end = toInt(entry[1]);
    } else if (typeof entry === "object") {
      start = toInt((entry as OffsetSpan).start);
      end = toInt((entry as OffsetSpan).end);
    }
    if (typeof start === "number" && typeof end === "number" && end > start) {
      spans.push({ start, end });
    }
  }
  return spans;
}

function matchSegmentId(segment: TraceSegment | null | undefined, expected: number | string | undefined): boolean {
  if (expected == null) return true;
  const segId = segment?.segment_id ?? (segment as any)?.id ?? (segment as any)?.segmentId;
  const seg = toInt(segId);
  const exp = toInt(expected);
  if (seg == null || exp == null) return true;
  return seg === exp;
}

function iterateCandidates(trace: TraceBody | null | undefined, segmentId?: number | string) {
  const dispatch = trace?.dispatch ?? {};
  const segments = Array.isArray(dispatch.segments) ? dispatch.segments : [];
  const buckets: TraceCandidate[] = [];
  for (const segment of segments) {
    if (!matchSegmentId(segment, segmentId)) continue;
    const candidates = Array.isArray(segment?.candidates) ? segment?.candidates : [];
    for (const cand of candidates) {
      if (cand) buckets.push(cand);
    }
  }
  if (!buckets.length) {
    const fallback = Array.isArray(dispatch.candidates) ? dispatch.candidates : [];
    for (const cand of fallback) {
      if (cand) buckets.push(cand);
    }
  }
  return buckets;
}

function collectOffsetsFromCandidate(candidate: TraceCandidate | null | undefined): OffsetSpan[] {
  if (!candidate) return [];
  const reasons = Array.isArray(candidate.reasons) ? candidate.reasons : [];
  const spans: OffsetSpan[] = [];
  for (const reason of reasons) {
    const offsets = Array.isArray(reason?.offsets) ? reason?.offsets : [];
    spans.push(...extractOffsets(offsets as OffsetLike[]));
  }
  return spans;
}

export function traceOffsetsForFinding(trace: TraceBody | null | undefined, finding: AnalyzeFindingEx): OffsetSpan[] {
  if (!trace || !finding?.rule_id) return [];
  const segmentId = (finding as any)?.segment_id ?? (finding as any)?.segmentId ?? (finding as any)?.segment?.id;
  const ruleId = String(finding.rule_id);
  const seen = new Set<string>();
  const collected: OffsetSpan[] = [];
  for (const candidate of iterateCandidates(trace, segmentId)) {
    if (!candidate || String(candidate.rule_id ?? "") !== ruleId) continue;
    for (const span of collectOffsetsFromCandidate(candidate)) {
      const key = `${span.start}:${span.end}`;
      if (seen.has(key)) continue;
      seen.add(key);
      collected.push(span);
      if (collected.length >= 4) return collected;
    }
  }
  return collected.slice(0, 4);
}

export type { TraceBody };
