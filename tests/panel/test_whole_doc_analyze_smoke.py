import json
import subprocess
import textwrap

# RAW string: отдаём JS ровно как нужно; \n — двойным слешем.
JS = r"""
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const bundlePath = path.resolve(process.cwd(), 'word_addin_dev', 'taskpane.bundle.js');
let code = fs.readFileSync(bundlePath, 'utf-8');
// Не пускаем bootstrap() автоматически.
code = code.replace(/bootstrap\(\);\s*$/, '');

let analyzeCalled = 0;
let annotateCalled = 0;
let findingsLen = 0;

const btnAnalyze = {
  handler: null,
  addEventListener(ev, fn) { if (ev === 'click') this.handler = fn; },
  removeAttribute() {},
  classList: { remove() {} },
  click() { this.handler && this.handler({ preventDefault(){} }); }
};

const elements = {
  btnAnalyze,
  results: { dispatchEvent() {} }
};

const document = {
  querySelector(sel) { return sel === '#btnAnalyze' ? btnAnalyze : null; },
  getElementById(id) { return elements[id] || null; },
  body: { dispatchEvent() {} }
};

const sandbox = {
  window: {},
  document,
  getWholeDocText: async () => 'A\nB\nC',
  apiAnalyze: async () => {
    analyzeCalled += 1;
    return {
      json: { analysis: { findings: [{ snippet: 'B', rule_id: 'governing_law_basic', severity: 'high', start: 2, end: 3, law_reference: 'Rome I / UCTA 1977' }] } },
      resp: {}
    };
  },
  annotateFindingsIntoWord: async (findings) => {
    if (Array.isArray(findings)) {
      findingsLen = findings.length;
      annotateCalled += 1;
    }
  },
  notifyOk: () => {},
  notifyErr: () => {},
  notifyWarn: () => {},
  applyMetaToBadges: () => {},
  metaFromResponse: () => ({}),
  console,
  CustomEvent: function(type, init){ return { type, detail: (init && init.detail) || null }; },
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);
sandbox.getWholeDocText = async () => 'A\nB\nC';
sandbox.apiAnalyze = async () => {
  analyzeCalled += 1;
  return {
    json: { analysis: { findings: [{ snippet: 'B', rule_id: 'governing_law_basic', severity: 'high', start: 2, end: 3, law_reference: 'Rome I / UCTA 1977' }] } },
    resp: {}
  };
};
sandbox.annotateFindingsIntoWord = async (findings) => {
  if (Array.isArray(findings)) {
    findingsLen = findings.length;
    annotateCalled += 1;
  }
};
sandbox.parseFindings = (resp) => {
  const arr = resp?.analysis?.findings || resp?.findings || resp?.issues || [];
  return Array.isArray(arr) ? arr.filter(Boolean) : [];
};

// wire + click Analyze
sandbox.wireUI();
btnAnalyze.click();

// Последняя строка — JSON для ассертов в Python (ждём завершения async)
setTimeout(() => {
  console.log(JSON.stringify({ analyze_called: analyzeCalled, annotate_called: annotateCalled, findings_len: findingsLen }));
}, 0);
"""


def test_whole_doc_analyze_smoke(tmp_path):
    """Analyze must trigger auto-annotation with non-empty findings."""
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(JS)],
        capture_output=True, text=True, check=True
    )
    last_line = result.stdout.strip().splitlines()[-1]
    data = json.loads(last_line)
    assert data.get("analyze_called") == 1
    assert data.get("annotate_called") == 1
    assert data.get("findings_len") >= 1

