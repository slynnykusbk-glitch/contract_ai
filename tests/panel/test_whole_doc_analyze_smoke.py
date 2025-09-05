import subprocess
import textwrap


JS = textwrap.dedent('''
const vm = require('vm');
const fs = require('fs');
let code = fs.readFileSync('word_addin_dev/taskpane.bundle.js', 'utf-8');
code = code.replace(/bootstrap\(\);\s*$/, '');

const ann = [];
const btnAnalyze = {
  handler: null,
  addEventListener(ev, fn) { if (ev === 'click') this.handler = fn; },
  removeAttribute() {},
  classList: { remove() {} },
  click() { this.handler && this.handler({ preventDefault(){} }); }
};

const elements = { btnAnalyze, results: { dispatchEvent() {} } };
const document = {
  querySelector(sel) { return sel === '#btnAnalyze' ? btnAnalyze : null; },
  getElementById(id) { return elements[id] || null; },
  body: { dispatchEvent() {} }
};

const sandbox = {
  window: {},
  document,
  getWholeDocText: async () => 'A\nB\nC',
  apiAnalyze: async () => ({ json: { analysis: { findings: [{ snippet: 'B', rule_id: 'r1', severity: 's' }] } }, resp: {} }),
  annotateFindingsIntoWord: async (findings) => { ann.push(findings); },
  notifyOk: () => {},
  notifyErr: () => {},
  notifyWarn: () => {},
  applyMetaToBadges: () => {},
  metaFromResponse: () => ({}),
  console,
  CustomEvent: function(type, init){ return { type, detail: init.detail }; },
  ann
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);
sandbox.wireUI();
btnAnalyze.click();
console.log(JSON.stringify(sandbox.ann.length));
''')


def test_whole_doc_analyze_smoke(tmp_path):
    script = tmp_path / 'run.js'
    script.write_text(JS)
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == '1'

