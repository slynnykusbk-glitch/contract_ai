require('ts-node/register');
const { dedupeFindings } = require('../../word_addin_dev/app/assets/dedupe.js');

describe('dedupe.removes-duplicates', () => {
  it('removes duplicates and preserves order', () => {
    const list = [
      { rule_id: 'r1', start: 0, end: 5, snippet: 'abcde', severity: 'low' },
      { rule_id: 'r1', start: 0, end: 5, snippet: 'abcde', severity: 'high' },
      { rule_id: 'r2', start: 6, end: 8, snippet: 'fg', severity: 'medium' },
      { rule_id: 'r1', start: 0, end: 5, snippet: 'abcde', severity: 'medium' },
    ];
    const res = dedupeFindings(list);
    expect(res.length).toBe(2);
    expect(res[0].rule_id).toBe('r1');
    expect(res[0].severity).toBe('high');
    expect(res[1].rule_id).toBe('r2');
  });
});
