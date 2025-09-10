require('ts-node/register');
const { dedupeFindings } = require('../../word_addin_dev/app/assets/taskpane');

describe('dedupeFindings', () => {
  it('removes duplicates and invalid ranges', () => {
    const input = [
      { rule_id: 'r', start: 0, end: 5, snippet: 'abcde', severity: 'low' },
      { rule_id: 'r', start: 0, end: 5, snippet: 'abcde', severity: 'high' },
      { rule_id: 'r2', start: 10, end: 9, snippet: 'bad' },
      { rule_id: 'r3', start: 0, end: 20000, snippet: 'xxxxx' }
    ];
    const out = dedupeFindings(input);
    expect(out.length).toBe(1);
    expect(out[0].severity).toBe('high');
  });
});
