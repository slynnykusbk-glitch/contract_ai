import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { planAnnotations } from '../assets/annotate';

describe('planAnnotations dedupe and overlap handling', () => {
  beforeEach(() => {
    (globalThis as any).__lastAnalyzed = 'alpha beta gamma delta epsilon zeta';
  });

  afterEach(() => {
    delete (globalThis as any).__lastAnalyzed;
  });

  it('deduplicates identical findings and skips overlapping ranges', () => {
    const findings = [
      { rule_id: 'A', snippet: 'alpha', start: 0, end: 5, severity: 'high', advice: 'alpha-high' },
      {
        rule_id: 'A',
        snippet: 'alpha',
        start: 0,
        end: 5,
        severity: 'medium',
        advice: 'alpha-medium',
      },
      {
        rule_id: 'B',
        snippet: 'beta',
        start: 6,
        end: 10,
        severity: 'medium',
        advice: 'beta-advice',
      },
      {
        rule_id: 'C',
        snippet: 'beta gamma',
        start: 8,
        end: 18,
        severity: 'critical',
        advice: 'overlap-advice',
      },
      { rule_id: 'D', snippet: 'delta', start: 20, end: 25, severity: 'low', advice: 'delta-low' },
      {
        rule_id: 'D',
        snippet: 'delta',
        start: 20,
        end: 25,
        severity: 'critical',
        advice: 'delta-critical',
      },
    ];

    const plan = planAnnotations(findings as any);
    expect(plan).toHaveLength(3);
    const order = plan.map(op => op.rule_id);
    expect(order).toEqual(['A', 'B', 'D']);

    const alpha = plan.find(op => op.rule_id === 'A');
    expect(alpha?.msg).toContain('alpha-high');
    const delta = plan.find(op => op.rule_id === 'D');
    expect(delta?.msg).toContain('delta-critical');
    const hasOverlap = plan.some(op => op.rule_id === 'C');
    expect(hasOverlap).toBe(false);
  });
});
