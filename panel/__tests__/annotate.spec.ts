import { annotateFindingsIntoWord } from '../../word_addin_dev/app/assets/taskpane';

describe('annotateFindingsIntoWord', () => {
  it('skips overlapping ranges and warns', async () => {
    const inserted: string[] = [];
    (global as any).__lastAnalyzed = 'abcdefghij';

    (global as any).Word = {
      run: async (fn: any) => {
        const ctx = {
          document: {
            body: {
              search: () => ({
                items: [{ insertComment: (msg: string) => { inserted.push(msg); } }],
                load: () => {}
              })
            }
          },
          sync: async () => {}
        } as any;
        return fn(ctx);
      }
    };

    const warns: string[] = [];
    (global as any).notifyWarn = (msg: string) => { warns.push(msg); };

    await annotateFindingsIntoWord([
      { start: 0, end: 5, snippet: 'abcde', rule_id: 'r1', severity: 'high' },
      { start: 3, end: 8, snippet: 'defgh', rule_id: 'r2', severity: 'medium' }
    ] as any);

    expect(inserted.length).toBe(1);
    expect(warns[0]).toMatch(/Skipped 1 overlaps/);
  });
});
