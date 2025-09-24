import json
import subprocess
import textwrap

JS = r"""
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const bundlePath = path.resolve(process.cwd(), 'word_addin_dev', 'taskpane.bundle.js');
let code = fs.readFileSync(bundlePath, 'utf-8');
code = code.replace(/bootstrap\(\);\s*$/, '');

let annotateCalled = 0;
let analyzeCalled = 0;

const btnAnalyze = {
  handler: null,
  addEventListener(ev, fn) { if (ev === 'click') this.handler = fn; },
  removeAttribute() {},
  classList: { remove() {} },
  click() { this.handler && this.handler({ preventDefault(){} }); }
};

const checkbox = { checked: true };

const elements = {
  btnAnalyze,
  results: { dispatchEvent() {} },
  'cai-comment-on-analyze': checkbox
};

const document = {
  querySelector(sel) { return sel === '#btnAnalyze' ? btnAnalyze : null; },
  getElementById(id) { return elements[id] || null; },
  body: { dispatchEvent() {} }
};

const sandbox = {
  window: {},
  document,
  getWholeDocText: async () => 'A',
  apiAnalyze: async () => {
    analyzeCalled += 1;
    return { json: { analysis: { findings: [{ snippet: 'A', rule_id: 'r1', severity: 'high' }] } }, resp: {} };
  },
  annotateFindingsIntoWord: async () => { annotateCalled += 1; },
  notifyOk: () => {},
  notifyErr: () => {},
  notifyWarn: () => {},
  applyMetaToBadges: () => {},
  metaFromResponse: () => ({}),
  console,
  CustomEvent: function(type, init){ return { type, detail: (init && init.detail) || null }; },
  parseFindings: (resp) => resp.analysis.findings
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

sandbox.wireUI();
btnAnalyze.click();
setTimeout(() => {
  const first = annotateCalled;
  checkbox.checked = false;
  btnAnalyze.click();
  setTimeout(() => {
    console.log(JSON.stringify({ first, second: annotateCalled }));
  }, 0);
}, 0);
"""


def test_autocomment_toggle(tmp_path):
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(JS)], capture_output=True, text=True, check=True
    )
    last_line = result.stdout.strip().splitlines()[-1]
    data = json.loads(last_line)
    assert data.get("first") == 1
    assert data.get("second") == 1
