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

const btnAnalyze = {
  handler: null,
  addEventListener(ev, fn) { if (ev === 'click') this.handler = fn; },
  removeAttribute() {},
  classList: { remove() {} },
  click() { this.handler && this.handler({ preventDefault(){} }); }
};

const select = { value: 'high' };
const vh = { textContent: '' };
const total = { textContent: '' };
const findingsList = { innerHTML: '', items: [], appendChild(li){ this.items.push(li); } };

const elements = {
  btnAnalyze,
  results: { dispatchEvent() {} },
  selectRiskThreshold: select,
  resFindingsVH: vh,
  resFindingsCount: total,
  findingsList
};

const document = {
  querySelector(sel) { return sel === '#btnAnalyze' ? btnAnalyze : null; },
  getElementById(id) { return elements[id] || null; },
  body: { dispatchEvent() {} },
  createElement(tag) { return { textContent: '' }; }
};

let warns = [];
const sandbox = {
  window: {},
  document,
  getWholeDocText: async () => 'abc',
  apiAnalyze: async () => ({ json: { analysis: {
    findings: [
      { snippet: 'a', rule_id: 'l', severity: 'low' },
      { snippet: 'b', rule_id: 'm', severity: 'medium' },
      { snippet: 'c', rule_id: 'h', severity: 'high' }
    ],
    coverage: { rules_fired: 3 }
  } }, resp: {} }),
  annotateFindingsIntoWord: async () => {},
  notifyOk: () => {},
  notifyErr: () => {},
  notifyWarn: (msg) => { warns.push(msg); },
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
  const parts = vh.textContent.split('/');
  const visible = parseInt(parts[0], 10);
  const hidden = parseInt(parts[1], 10);
  const totalCount = parseInt(total.textContent, 10);
  console.log(JSON.stringify({ visible, hidden, total: totalCount, warns }));
}, 0);
"""


def test_filters_visibility(tmp_path):
    result = subprocess.run([
        "node",
        "-e",
        textwrap.dedent(JS),
    ], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["visible"] + data["hidden"] == data["total"] == 3

