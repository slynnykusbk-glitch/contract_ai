import { describe, it, expect, beforeEach } from 'vitest';
import type { AnalyzeFinding } from '../assets/api-client';
import { annotate } from '../assets/annotate';

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

    const ops = annotate(findings);
    expect(ops.length).toBe(2);
    const map = Object.fromEntries(ops.map(o => [o.rule_id, o.occIdx]));
    expect(map['r1']).toBe(0);
    expect(map['r2']).toBe(1);
  });

  it('returns empty array for invalid findings', () => {
    const findings: AnalyzeFinding[] = [
      { start: undefined, end: undefined, snippet: '', rule_id: 'r1' },
    ];
    const ops = annotate(findings);
    expect(ops.length).toBe(0);
  });
});

