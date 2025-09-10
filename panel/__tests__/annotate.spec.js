require('ts-node/register');
const { annotateFindingsIntoWord } = require('../../word_addin_dev/app/assets/taskpane');

describe('annotateFindingsIntoWord', () => {
  it('skips overlapping ranges and warns', async () => {
    const inserted = [];
    global.__lastAnalyzed = 'abcdefghij';

    global.Word = {
      run: async fn => {
        const ctx = {
          document: {
            body: {
              search: () => ({
                items: [{ insertComment: msg => { inserted.push(msg); } }],
                load: () => {}
              })
            }
          },
          sync: async () => {}
        };
        return fn(ctx);
      }
    };

    const warns = [];
    global.notifyWarn = msg => { warns.push(msg); };

    await annotateFindingsIntoWord([
      { start: 0, end: 5, snippet: 'abcde', rule_id: 'r1', severity: 'high' },
      { start: 3, end: 8, snippet: 'defgh', rule_id: 'r2', severity: 'medium' }
    ]);

    expect(inserted.length).toBe(1);
    expect(warns[0]).toMatch(/Skipped 1 overlaps/);
  });
});
