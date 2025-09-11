require('ts-node/register');
global.window = global;
 const stubEl = {
  style: {},
  addEventListener: () => {},
  removeEventListener: () => {},
  innerHTML: '',
  textContent: '',
  classList: { add: () => {}, remove: () => {}, contains: () => false },
  removeAttribute: () => {},
  setAttribute: () => {}
};
 global.document = {
  getElementById: () => stubEl,
  querySelector: () => stubEl,
  querySelectorAll: () => ({ forEach: () => {} }),
  body: { dataset: {}, querySelectorAll: () => ({ forEach: () => {} }) }
};
global.notifyWarn = jest.fn();
global.notifyOk = jest.fn();
global.localStorage = { getItem: () => null, setItem: () => {} };
global.CAI = { Store: { get: () => ({}) } };
global.__CAI_TESTING__ = true;
jest.mock('../../word_addin_dev/app/assets/store', () => ({
  getAddCommentsFlag: () => false,
  setAddCommentsFlag: () => {},
}));
jest.mock('../../word_addin_dev/app/assets/notifier', () => ({
  notifyWarn: jest.fn(),
  notifyOk: jest.fn(),
  notifyErr: jest.fn(),
}));
const { annotateFindingsIntoWord } = require('../../word_addin_dev/app/assets/taskpane');

describe('annotateFindingsIntoWord inserts', () => {
  beforeEach(() => {
    global.notifyWarn.mockClear();
    global.notifyOk.mockClear();
  });

  it('does not reuse Range from another run', async () => {
    let currentRun = 0;
    global.Word = {
      run: async fn => {
        currentRun++;
        const runId = currentRun;
        const ctx = {
          document: {
            body: {
              search: () => ({
                items: [{
                  runId,
                  insertComment(msg) {
                    if (runId !== currentRun) throw new Error('InvalidObjectPath');
                  },
                }],
                load: () => {}
              })
            }
          },
          sync: async () => {}
        };
        return fn(ctx);
      }
    };

    const findings = Array.from({ length: 25 }, (_, i) => ({
      snippet: 'a',
      rule_id: `r${i}`,
      start: i,
      end: i + 1,
      severity: 'low'
    }));
    await expect(annotateFindingsIntoWord(findings)).resolves.toBe(25);
  });

  it('batches insertions by 20', async () => {
    let runs = 0;
    global.Word = {
      run: async fn => {
        runs++;
        const ctx = {
          document: {
            body: {
              search: () => ({ items: [{ insertComment: () => {} }], load: () => {} })
            }
          },
          sync: async () => {}
        };
        return fn(ctx);
      }
    };

    const findings = Array.from({ length: 35 }, (_, i) => ({
      snippet: `x${i}`,
      rule_id: `r${i}`,
      start: i,
      end: i + 1,
      severity: 'low'
    }));
    await annotateFindingsIntoWord(findings);
    expect(runs).toBe(2);
  });

  it('falls back to normalized snippet when raw not found', async () => {
    let inserted = 0;
    global.Word = {
      run: async fn => {
        const ctx = {
          document: {
            body: {
              search: txt => ({
                items: txt === 'foo  bar' ? [] : [{ insertComment: () => { inserted++; } }],
                load: () => {}
              })
            }
          },
          sync: async () => {}
        };
        return fn(ctx);
      }
    };

    const finding = { snippet: 'foo  bar', rule_id: 'r1', start: 0, end: 7, severity: 'low' };
    await annotateFindingsIntoWord([finding]);
    expect(inserted).toBe(1);
  });
});
