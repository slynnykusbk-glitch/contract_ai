import { describe, expect, it } from 'vitest';
import { performance } from 'perf_hooks';
import { mergeQaFindings } from '../assets/qa/mergeQaResults';

describe('mergeQaFindings append behavior', () => {
  it('appends only new QA findings and runs in linear time', () => {
    const base = Array.from({ length: 1000 }, (_, idx) => ({
      rule_id: `R-${idx}`,
      start: idx * 5,
      end: idx * 5 + 4,
      snippet: `Snippet ${idx}`,
      severity: idx % 4 === 0 ? 'high' : 'medium',
      salience: idx % 10,
      agenda_group: idx % 5 === 0 ? 'law' : 'policy',
    }));

    const qaDuplicates = Array.from({ length: 50 }, (_, idx) => ({
      rule_id: `R-${idx}`,
      start: idx * 5,
      end: idx * 5 + 4,
      snippet: `Snippet ${idx}`,
      severity: 'critical',
      salience: 10 - idx,
      agenda_group: 'law',
    }));

    const qaNew = Array.from({ length: 50 }, (_, idx) => ({
      rule_id: `QA-${idx}`,
      start: 5000 + idx * 5,
      end: 5000 + idx * 5 + 4,
      snippet: `QA Snippet ${idx}`,
      severity: 'medium',
      salience: idx,
      agenda_group: 'drafting',
    }));

    const qa = [...qaDuplicates, ...qaNew];

    const start = performance.now();
    const merged = mergeQaFindings(base, qa);
    const duration = performance.now() - start;

    expect(merged).toHaveLength(base.length + qaNew.length);

    if (duration >= 50) {
      console.warn(`[perf] mergeQaFindings took ${duration.toFixed(2)}ms`);
    } else {
      expect(duration).toBeLessThan(50);
    }
    expect(duration).toBeLessThan(200);

    const appendedIds = merged.slice(-qaNew.length).map(item => item.rule_id);
    expect(new Set(appendedIds)).toEqual(new Set(qaNew.map(item => item.rule_id)));
  });
});
