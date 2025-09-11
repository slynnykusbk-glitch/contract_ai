import json
import subprocess
import textwrap

JS = r"""
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const bundlePath = path.resolve(process.cwd(), 'word_addin_dev', 'taskpane.bundle.js');
let code = fs.readFileSync(bundlePath, 'utf-8');
code = code.replace(/bootstrap\(\);/g, '');

const comments = [];
const snippet = 'foo   bar';
const norm = 'foo bar';

const sandbox = {
  window: { __lastAnalyzed: snippet },
  document: { readyState: 'complete', getElementById(){return { style:{}, disabled:false };}, querySelector(){return null;}, addEventListener(){}, body: { dispatchEvent() {} } },
  Word: {
    run: async (fn) => {
      const ctx = {
        document: {
          body: {
            search: (txt) => ({
              items: txt === snippet ? [] : (txt === norm ? [{ insertComment: (msg) => comments.push(msg) }] : []),
              load: () => {}
            })
          }
        },
        sync: async () => {}
      };
      await fn(ctx);
    }
  },
  console
};

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

(async () => {
  await sandbox.annotateFindingsIntoWord([{ snippet, normalized_snippet: norm, rule_id: 'r1', severity: 'high', start: 0 }]);
  console.log(JSON.stringify(comments));
})();
"""


def test_anchor_fallbacks(tmp_path):
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(JS)], capture_output=True, text=True, check=True
    )
    last_line = result.stdout.strip().splitlines()[-1]
    data = json.loads(last_line)
    assert len(data) == 1
