import json
import subprocess
import textwrap
from pathlib import Path

TEXT = Path("tests/fixtures/quality_clause13.txt").read_text().strip()
SNIPPETS = [s.strip() for s in TEXT.split(".") if s.strip()]
FINDINGS = [
    {"snippet": SNIPPETS[0], "rule_id": "13.ITP.EXISTS", "severity": "high", "start": 0},
    {"snippet": SNIPPETS[1], "rule_id": "13.SHIP.BLOCK", "severity": "high", "start": len(SNIPPETS[0]) + 2},
    {"snippet": SNIPPETS[2], "rule_id": "13.EQUIP.CERT.LOLER_PUWER", "severity": "high", "start": len(SNIPPETS[0]) + len(SNIPPETS[1]) + 4},
]

DOC_TEXT = json.dumps(TEXT)
FINDINGS_JSON = json.dumps(FINDINGS)

JS_TEMPLATE = r"""
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const bundlePath = path.resolve(process.cwd(), 'word_addin_dev', 'taskpane.bundle.js');
let code = fs.readFileSync(bundlePath, 'utf-8');
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
  getWholeDocText: async () => '',
  apiAnalyze: async () => ({ json: { analysis: { findings: [] } }, resp: {} }),
  annotateFindingsIntoWord: async () => {},
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

sandbox.getWholeDocText = async () => __TEXT__;
sandbox.apiAnalyze = async () => {
  analyzeCalled += 1;
  return {
    json: { analysis: { findings: __FINDINGS__ } },
    resp: {},
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

sandbox.wireUI();
btnAnalyze.click();

setTimeout(() => {
  console.log(JSON.stringify({ analyze_called: analyzeCalled, annotate_called: annotateCalled, findings_len: findingsLen }));
}, 0);
"""

JS = JS_TEMPLATE.replace('__TEXT__', DOC_TEXT).replace('__FINDINGS__', FINDINGS_JSON)


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
