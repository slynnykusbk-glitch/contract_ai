const { dedupeFindings } = require('../../build/dedupe.js');

describe('dedupeFindings', () => {
  it('returns single entry for exact duplicates', () => {
    const sample = { rule_id: 'r', start: 0, end: 5, snippet: 'abcde' };
    const input = Array.from({ length: 5 }, () => ({ ...sample }));
    const out = dedupeFindings(input);
    expect(out.length).toBe(1);
  });

  it('keeps findings with different ranges', () => {
    const base = { rule_id: 'r', snippet: 'abcde' };
    const input = [
      { ...base, start: 0, end: 5 },
      { ...base, start: 1, end: 6 },
      { ...base, start: 2, end: 7 }
    ];
    const out = dedupeFindings(input);
    expect(out.length).toBe(3);
  });
});
