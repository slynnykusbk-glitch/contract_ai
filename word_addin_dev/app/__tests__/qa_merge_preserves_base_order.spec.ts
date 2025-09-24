import { describe, expect, it } from 'vitest';
import { mergeQaFindings } from '../assets/qa/mergeQaResults';

describe('mergeQaFindings - base order preservation', () => {
  it('replaces duplicates in place and appends new QA findings', () => {
    const base = [
      { rule_id: 'A', start: 0, end: 10, snippet: 'Alpha', severity: 'low', agenda_group: 'law', salience: 0.5, source: 'analyze', message: 'Base A' },
      { rule_id: 'B', start: 11, end: 20, snippet: 'Beta', severity: 'medium', agenda_group: 'policy', salience: 0.4, source: 'analyze', message: 'Base B' },
      { rule_id: 'C', start: 21, end: 30, snippet: 'Gamma', severity: 'low', agenda_group: 'drafting', salience: 0.3, source: 'analyze', message: 'Base C' },
    ];

    const qa = [
      { rule_id: 'B', start: 11, end: 20, snippet: 'Beta', severity: 'high', agenda_group: 'policy', salience: 0.6, message: 'QA B prime' },
      { rule_id: 'D', start: 31, end: 40, snippet: 'Delta', severity: 'medium', agenda_group: 'grammar', salience: 0.2, message: 'QA D' },
    ];

    const merged = mergeQaFindings(base, qa);

    expect(merged).toHaveLength(4);
    expect(merged.map(item => item.rule_id)).toEqual(['A', 'B', 'C', 'D']);
    expect(merged[1].message).toBe('QA B prime');
    expect(merged[1].severity).toBe('high');
    expect(merged[1].salience).toBe(0.6);
    expect(merged[1].agenda_group).toBe('policy');
    expect(merged[1]).not.toBe(base[1]);
    expect(base[1].message).toBe('Base B');
    expect(merged[3].rule_id).toBe('D');
    expect((merged[3] as any).source).toBe('qa');
  });
});
