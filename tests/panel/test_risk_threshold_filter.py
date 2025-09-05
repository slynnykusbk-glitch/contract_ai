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
let receivedRuleIds = [];

const btnAnalyze = {
  handler: null,
  addEventListener(ev, fn) { if (ev === 'click') this.handler = fn; },
  removeAttribute() {},
  classList: { remove() {} },
  click() { this.handler && this.handler({ preventDefault(){} }); }
};

const select = { value: 'high' };
const checkbox = { checked: true };

const elements = {
  btnAnalyze,
  results: { dispatchEvent() {} },
  'selectRiskThreshold': select,
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
  getWholeDocText: async () => 'abc',
  apiAnalyze: async () => ({ json: { analysis: { findings: [
    { snippet: 'a', rule_id: 'low', severity: 'low' },
    { snippet: 'b', rule_id: 'med', severity: 'medium' },
    { snippet: 'c', rule_id: 'hi', severity: 'high' }
  ] } }, resp: {} }),
  annotateFindingsIntoWord: async (list) => { annotateCalled += 1; receivedRuleIds = list.map(f => f.rule_id); },
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
  console.log(JSON.stringify({ annotateCalled, receivedRuleIds }));
}, 0);
"""

def test_risk_threshold_filter(tmp_path):
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(JS)],
        capture_output=True, text=True, check=True
    )
    last_line = result.stdout.strip().splitlines()[-1]
    data = json.loads(last_line)
    assert data.get("annotateCalled") == 1
    assert data.get("receivedRuleIds") == ["hi"]
