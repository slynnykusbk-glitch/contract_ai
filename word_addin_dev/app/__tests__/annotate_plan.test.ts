import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { AnalyzeFinding } from '../assets/api-client';
import {
  planAnnotations,
  MAX_ANNOTATE_OPS,
  annotateFindingsIntoWord,
  COMMENT_PREFIX,
} from '../assets/annotate';
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

  it('deduplicates identical findings', () => {
    const findings: AnalyzeFinding[] = [
      { start: 0, end: 3, snippet: 'abc', rule_id: 'r1' },
      { start: 0, end: 3, snippet: 'abc', rule_id: 'r1' },
    ];
    const ops = planAnnotations(findings);
    expect(ops.length).toBe(1);
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

  it('includes quote and clause link in comment', () => {
    const findings: AnalyzeFinding[] = [
      {
        start: 0,
        end: 3,
        snippet: 'abc',
        rule_id: 'r1',
        norm_quote: 'norm',
        clause_url: 'http://example.com/clause/1',
        clause_id: '1',
      },
    ];
    const ops = planAnnotations(findings);
    expect(ops[0].msg).toContain('norm');
    expect(ops[0].msg).toContain('http://example.com/clause/1');
  });

  it('merges overlapping anchors', async () => {
    const body = {
      context: { sync: async () => {}, trackedObjects: { add: () => {} } },
      search: () => ({
        items: [
          { start: 0, end: 5 },
          { start: 3, end: 7 },
          { start: 10, end: 12 },
        ],
        load: () => {},
      }),
    } as any;
    const res = await findAnchors(body, 'dummy');
    expect(res).toEqual([
      { start: 0, end: 5 },
      { start: 10, end: 12 },
    ]);
  });

  it('skips findings with no anchors', async () => {
    const body = {
      context: { sync: async () => {}, trackedObjects: { add: () => {} } },
      search: () => ({ items: [], load: () => {} }),
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
      rule_id: `r${i}`,
    }));
    const ops = planAnnotations(findings);
    expect(ops.length).toBe(MAX_ANNOTATE_OPS);
  });

  it('annotates findings on correct ranges with prefix', async () => {
    const findings: AnalyzeFinding[] = [{ start: 0, end: 3, snippet: 'abc', rule_id: 'r1' }];
    const inserted: string[] = [];
    const ranges = [
      { start: 0, end: 3, load: () => {}, insertComment: (msg: string) => inserted.push(msg) },
    ];
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } };
    (globalThis as any).Word = {
      run: async (cb: any) => {
        const ctx = {
          document: {
            body: {
              context: { sync: async () => {}, trackedObjects: { add: () => {} } },
              search: () => ({ items: ranges, load: () => {} }),
            },
          },
          sync: async () => {},
        };
        return await cb(ctx);
      },
    };
    const count = await annotateFindingsIntoWord(findings);
    expect(count).toBe(1);
    expect(inserted[0].startsWith(COMMENT_PREFIX)).toBe(true);
  });

  it('handles very long snippets gracefully', async () => {
    const long = 'a'.repeat(5000);
    const findings: AnalyzeFinding[] = [
      { start: 0, end: long.length, snippet: long, rule_id: 'r1' },
    ];
    const plan = planAnnotations(findings);
    expect(plan.length).toBe(1);

    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    (globalThis as any).Word = {
      run: async (cb: any) => {
        const body = {
          context: { sync: async () => {}, trackedObjects: { add: () => {} } },
          search: () => {
            const err: any = new Error('fail');
            err.code = 'SearchStringInvalidOrTooLong';
            throw err;
          },
        } as any;
        const ctx = { document: { body }, sync: async () => {} };
        return await cb(ctx);
      },
    };
    const inserted = await annotateFindingsIntoWord(findings);
    expect(inserted).toBe(0);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
