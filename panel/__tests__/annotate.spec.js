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
let mockWarns = [];
jest.mock('../../word_addin_dev/app/assets/notifier', () => ({
  notifyWarn: (msg) => { mockWarns.push(msg); },
  notifyOk: jest.fn(),
  notifyErr: jest.fn(),
}));
jest.mock('../../word_addin_dev/app/assets/store', () => ({
  getAddCommentsFlag: () => false,
  setAddCommentsFlag: () => {},
}));
global.localStorage = { getItem: () => null, setItem: () => {} };
global.CAI = { Store: { get: () => ({}) } };
global.__CAI_TESTING__ = true;
const { annotateFindingsIntoWord } = require('../../word_addin_dev/app/assets/taskpane');

describe('annotateFindingsIntoWord', () => {
  it('skips overlapping ranges and warns', async () => {
    mockWarns = [];
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

    mockWarns = [];
    global.notifyWarn = msg => { mockWarns.push(msg); };

    await annotateFindingsIntoWord([
      { start: 0, end: 5, snippet: 'abcde', rule_id: 'r1', severity: 'high' },
      { start: 3, end: 8, snippet: 'defgh', rule_id: 'r2', severity: 'medium' }
    ]);

    expect(inserted.length).toBe(1);
    expect(mockWarns[0]).toMatch(/Skipped 1 overlaps/);
  });
});
