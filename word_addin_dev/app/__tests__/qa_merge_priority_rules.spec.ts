import { describe, expect, it } from 'vitest';
import { priorityCompare } from '../assets/qa/mergeQaResults';

function makeFinding(overrides: Record<string, any> = {}) {
  return {
    rule_id: 'R-100',
    start: 0,
    end: 5,
    snippet: 'text',
    severity: 'medium',
    salience: 1,
    agenda_group: 'policy',
    ...overrides,
  };
}

describe('priorityCompare', () => {
  it('prefers higher severity first', () => {
    const high = makeFinding({ severity: 'high' });
    const low = makeFinding({ severity: 'low' });
    expect(priorityCompare(high, low)).toBeGreaterThan(0);
    expect(priorityCompare(low, high)).toBeLessThan(0);
  });

  it('prefers higher salience when severity ties', () => {
    const a = makeFinding({ salience: 0.8 });
    const b = makeFinding({ salience: 0.4 });
    expect(priorityCompare(a, b)).toBeGreaterThan(0);
    expect(priorityCompare(b, a)).toBeLessThan(0);
  });

  it('prefers agenda groups by backend ordering', () => {
    const law = makeFinding({ agenda_group: 'law', salience: 0 });
    const grammar = makeFinding({ agenda_group: 'grammar', salience: 0 });
    expect(priorityCompare(law, grammar)).toBeGreaterThan(0);
    expect(priorityCompare(grammar, law)).toBeLessThan(0);
  });

  it('falls back to rule_id ascending', () => {
    const a = makeFinding({ rule_id: 'A-1', salience: 0 });
    const b = makeFinding({ rule_id: 'B-1', salience: 0 });
    expect(priorityCompare(a, b)).toBeGreaterThan(0);
    expect(priorityCompare(b, a)).toBeLessThan(0);
    expect(priorityCompare(a, a)).toBe(0);
  });
});
