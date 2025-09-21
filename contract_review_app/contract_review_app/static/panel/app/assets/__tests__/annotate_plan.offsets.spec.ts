import { describe, it, expect, beforeEach, beforeAll } from 'vitest';

let computeNthFromOffsets: (typeof import('../annotate'))['computeNthFromOffsets'];
let planAnnotations: (typeof import('../annotate'))['planAnnotations'];
let parseFindings: (typeof import('../findings'))['parseFindings'];

beforeAll(async () => {
  (globalThis as any).window = globalThis as any;
  const annotateMod = await import('../annotate');
  computeNthFromOffsets = annotateMod.computeNthFromOffsets;
  planAnnotations = annotateMod.planAnnotations;
  const findingsMod = await import('../findings');
  parseFindings = findingsMod.parseFindings;
});
import type { AnalyzeFindingEx } from '../types';

const countOccurrences = (text: string, snippet: string) => {
  const starts: number[] = [];
  let idx = -1;
  while ((idx = text.indexOf(snippet, idx + 1)) !== -1) {
    starts.push(idx);
  }
  return starts;
};

describe('computeNthFromOffsets', () => {
  it('returns null when start is missing', () => {
    expect(computeNthFromOffsets('abc', 'a')).toBeNull();
  });

  it('returns null for empty normalized snippet', () => {
    expect(computeNthFromOffsets('abc', '   ', 0)).toBeNull();
  });

  it('counts occurrences before offset', () => {
    const text = 'foo bar foo bar foo bar';
    const snippet = 'foo bar';
    const starts = countOccurrences(text, snippet);
    const start = starts[1];
    expect(computeNthFromOffsets(text, snippet, start)).toBe(1);
  });

  it('handles offset at document start', () => {
    expect(computeNthFromOffsets('foo bar', 'foo', 0)).toBe(0);
  });

  it('supports offsets beyond text length', () => {
    const text = 'alpha beta alpha beta';
    const snippet = 'alpha';
    const starts = countOccurrences(text, snippet);
    const start = text.length + 5;
    expect(computeNthFromOffsets(text, snippet, start)).toBe(starts.length);
  });

  it('handles non ASCII punctuation', () => {
    const text = '«quote» «quote» «quote»';
    const snippet = '«quote»';
    const starts = countOccurrences(text, snippet);
    const start = starts[2];
    expect(computeNthFromOffsets(text, snippet, start)).toBe(2);
  });

  it('normalizes whitespace before counting', () => {
    const text = 'A\u00A0A foo A\u00A0A';
    const snippet = 'A\u00A0A';
    const start = text.lastIndexOf(snippet);
    expect(computeNthFromOffsets(text, snippet, start)).toBe(1);
  });

  it('property: matches raw occurrence index for random samples', () => {
    for (let i = 0; i < 100; i++) {
      const occ = Math.max(2, Math.floor(Math.random() * 5) + 1);
      const snippet = `word${i % 7}`;
      const parts: string[] = [];
      for (let j = 0; j < occ; j++) {
        parts.push(snippet);
        parts.push(` filler${j}`);
      }
      const text = parts.join(' ').trim();
      const starts = countOccurrences(text, snippet);
      const pick = starts[Math.floor(Math.random() * starts.length)];
      const nth = computeNthFromOffsets(text, snippet, pick);
      expect(nth).toBe(starts.indexOf(pick));
    }
  });
});

describe('parseFindings', () => {
  it('preserves start and end offsets', () => {
    const findings = parseFindings({
      analysis: {
        findings: [
          { rule_id: 'r1', snippet: 'foo', start: 5, end: 8 }
        ]
      }
    } as any);
    expect(findings[0].start).toBe(5);
    expect(findings[0].end).toBe(8);
  });
});

describe('planAnnotations offsets', () => {
  beforeEach(() => {
    (globalThis as any).__lastAnalyzed = 'foo bar foo bar foo bar';
  });

  it('stores nth computed from offsets', () => {
    const text = (globalThis as any).__lastAnalyzed as string;
    const snippet = 'foo bar';
    const starts = countOccurrences(text, snippet);
    const start = starts[2];
    const finding: AnalyzeFindingEx = { rule_id: 'r1', snippet, start, end: start + snippet.length } as any;
    const plan = planAnnotations([finding]);
    expect(plan[0].nth).toBe(2);
    expect(plan[0].occIdx).toBe(2);
    expect(plan[0].start).toBe(start);
    expect(plan[0].end).toBe(start + snippet.length);
  });

  it('falls back to first occurrence when snippet absent in text', () => {
    (globalThis as any).__lastAnalyzed = 'alpha beta gamma';
    const start = 0;
    const plan = planAnnotations([
      { rule_id: 'r2', snippet: 'delta', start, end: start + 5 } as any
    ]);
    expect(plan.length).toBe(1);
    expect(plan[0].nth).toBe(0);
    expect(plan[0].occIdx).toBe(0);
  });
});
