import { describe, expect, it } from 'vitest';
import { mergeQaFindings } from '../assets/qa/mergeQaResults';

describe('mergeQaFindings idempotency', () => {
  it('produces stable results when merging the same QA payload twice', () => {
    const base = [
      { rule_id: 'A', start: 0, end: 5, snippet: 'Alpha', severity: 'low', salience: 0.1, agenda_group: 'law' },
      { rule_id: 'B', start: 6, end: 10, snippet: 'Beta', severity: 'medium', salience: 0.2, agenda_group: 'policy' },
    ];
    const qa = [
      { rule_id: 'B', start: 6, end: 10, snippet: 'Beta', severity: 'high', salience: 0.4, agenda_group: 'policy' },
      { rule_id: 'C', start: 11, end: 15, snippet: 'Gamma', severity: 'medium', salience: 0.3, agenda_group: 'drafting' },
    ];

    const once = mergeQaFindings(base, qa);
    const twice = mergeQaFindings(once, qa);

    expect(twice).toEqual(once);
    expect(once).not.toBe(base);
  });
});
