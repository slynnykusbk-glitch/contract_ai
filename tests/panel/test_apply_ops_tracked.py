import json
import subprocess
import textwrap

JS = textwrap.dedent('''
const vm = require('vm');
const fs = require('fs');
let code = fs.readFileSync('word_addin_dev/taskpane.bundle.js', 'utf-8');
code = code.replace(/bootstrap\(\);/, '');
const inserts = [];
const sandbox = {
  window: { __lastAnalyzed: 'abc abc' },
  Word: {
    run: async (fn) => {
      const ctx = {
        document: {
          body: {
            search: () => ({
              items: [
                { insertText: (t) => inserts.push({idx:0, txt:t}), insertComment: () => {} },
                { insertText: (t) => inserts.push({idx:1, txt:t}), insertComment: () => {} }
              ],
              load: () => {}
            })
          },
          trackRevisions: false
        },
        sync: async () => {}
      };
      await fn(ctx);
    }
  },
  inserts
};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
(async () => {
  await sandbox.applyOpsTracked([{start:4,end:7,replacement:'XYZ'}]);
  console.log(JSON.stringify(sandbox.inserts));
})();
''')

def test_apply_ops_nth_occurrence(tmp_path):
    script = tmp_path / 'run.js'
    script.write_text(JS)
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip())
    assert data == [{'idx': 1, 'txt': 'XYZ'}]
