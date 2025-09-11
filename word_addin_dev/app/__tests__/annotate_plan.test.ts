import { describe, it, expect, beforeEach } from 'vitest';
import type { AnalyzeFinding } from '../assets/api-client';
import { planAnnotations, MAX_ANNOTATE_OPS } from '../assets/annotate';
import { findAnchors } from '../assets/anchors';


describe('annotate scheduler', () => {
  beforeEach(() => {
    // base text used to compute occurrence indexes
    (globalThis as any).__lastAnalyzed = 'abc def abc xyz';
  });

  it('computes ops and skips overlaps', () => {
    const findings: AnalyzeFinding[] = [
      { start: 0, end: 3, snippet: 'abc', rule_id: 'r1' },
      { start: 8, end: 11, snippet: 'abc', rule_id: 'r2' },
      // overlap with first finding, should be skipped
      { start: 2, end: 9, snippet: 'c def a', rule_id: 'r3' },
    ];

    const ops = planAnnotations(findings);
    expect(ops.length).toBe(2);
    const map = Object.fromEntries(ops.map(o => [o.rule_id, o.occIdx]));
    expect(map['r1']).toBe(0);
    expect(map['r2']).toBe(1);
  });

  it('returns empty array for invalid findings', () => {
    const findings: AnalyzeFinding[] = [
      { start: undefined, end: undefined, snippet: '', rule_id: 'r1' },
    ];
    const ops = planAnnotations(findings);
    expect(ops.length).toBe(0);
  });

  it('returns empty array for non-array input', () => {
    // @ts-expect-error deliberately passing invalid type
    const ops = planAnnotations('nope');
    expect(ops.length).toBe(0);
  });

  it('merges overlapping anchors', async () => {
    const body = {
      context: { sync: async () => {}, trackedObjects: { add: () => {} } },
      search: () => ({
        items: [
          { start: 0, end: 5 },
          { start: 3, end: 7 },
          { start: 10, end: 12 }
        ],
        load: () => {}
      })
    } as any;
    const res = await findAnchors(body, 'dummy');
    expect(res).toEqual([
      { start: 0, end: 5 },
      { start: 10, end: 12 }
    ]);
  });

  it('skips findings with no anchors', async () => {
    const body = {
      context: { sync: async () => {}, trackedObjects: { add: () => {} } },
      search: () => ({ items: [], load: () => {} })
    } as any;
    const finding: AnalyzeFinding = { start: 0, end: 3, snippet: 'abc', rule_id: 'r1' };
    const ops = planAnnotations([finding]);
    const anchors = await findAnchors(body, ops[0].raw);
    const skipped = anchors.length === 0 ? [ops[0]] : [];
    expect(skipped.length).toBe(1);
  });

  it('limits number of operations for big documents', () => {
    const findings: AnalyzeFinding[] = Array.from({ length: MAX_ANNOTATE_OPS + 25 }, (_, i) => ({
      start: i * 2,
      end: i * 2 + 1,
      snippet: 'x',
      rule_id: `r${i}`
    }));
    const ops = planAnnotations(findings);
    expect(ops.length).toBe(MAX_ANNOTATE_OPS);
  });
});

