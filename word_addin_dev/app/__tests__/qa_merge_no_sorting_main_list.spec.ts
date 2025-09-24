import { describe, expect, it, vi } from 'vitest';
import { mergeQaFindings } from '../assets/qa/mergeQaResults';

describe('mergeQaFindings does not sort results', () => {
  it('avoids calling Array.sort on the merged output', () => {
    const sortSpy = vi.spyOn(Array.prototype as any, 'sort');

    try {
      const base = [
        { rule_id: 'A', start: 0, end: 5, snippet: 'Alpha', severity: 'low', salience: 0.1, agenda_group: 'law' },
        { rule_id: 'B', start: 6, end: 10, snippet: 'Beta', severity: 'medium', salience: 0.2, agenda_group: 'policy' },
      ];
      const qa = [
        { rule_id: 'C', start: 11, end: 15, snippet: 'Gamma', severity: 'high', salience: 0.5, agenda_group: 'grammar' },
      ];

      mergeQaFindings(base, qa);
      expect(sortSpy).not.toHaveBeenCalled();
    } finally {
      sortSpy.mockRestore();
    }
  });
});
