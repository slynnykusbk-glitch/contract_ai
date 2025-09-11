require('ts-node/register');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

describe('counter.correct', () => {
  let sandbox;
  let logs;
  beforeEach(() => {
    logs = [];
    global.window = { __lastAnalyzed: 'abcdef' };
    global.document = { getElementById: () => ({ style: {}, addEventListener: () => {} }), querySelector: () => null, addEventListener: () => {}, body: { dispatchEvent() {} } };
    global.notifyOk = jest.fn();
    global.notifyWarn = jest.fn();
    global.Word = {
      run: async fn => {
        const ctx = {
          document: {
            body: {
              search: () => ({ items: [{ insertComment: () => {} }], load: () => {} }),
            },
            getSelection: () => ({ insertComment: () => {} }),
          },
          sync: async () => {},
        };
        return fn(ctx);
      }
    };
    const code = fs.readFileSync(path.resolve(__dirname, '../../word_addin_dev/app/assets/taskpane.js'), 'utf-8').replace(/bootstrap\(\);\s*$/, '');
    const base = path.resolve(__dirname, '../../word_addin_dev/app/assets');
    const consoleMock = { log: (m) => logs.push(m), warn: () => {}, error: () => {} };
    sandbox = { window: global.window, document: global.document, notifyOk: (m) => logs.push(`[OK] ${m}`), notifyWarn: () => {}, Word: global.Word, console: consoleMock, exports: {}, require: (p) => require(path.join(base, p + '.js')) };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
  });

  it('reports correct number after dedupe and overlap', async () => {
    const findings = [
      { rule_id: 'r1', start: 0, end: 5, snippet: 'abcde', severity: 'high', clause_type: 'x' },
      { rule_id: 'r1', start: 0, end: 5, snippet: 'abcde', severity: 'low', clause_type: 'x' },
      { rule_id: 'r2', start: 6, end: 8, snippet: 'fg', severity: 'medium', clause_type: 'y' },
    ];
    await sandbox.exports.annotateFindingsIntoWord(findings.filter(f => f.severity === 'high'));
    expect(logs.some(m => /Will insert: 1/.test(m))).toBe(true);
    await sandbox.exports.annotateFindingsIntoWord(findings);
    expect(logs.some(m => /Will insert: 2/.test(m))).toBe(true);
  });
});
