import json
import subprocess
import textwrap

JS = textwrap.dedent('''
const vm = require('vm');
const fs = require('fs');
let code = fs.readFileSync('word_addin_dev/taskpane.bundle.js', 'utf-8');
code = code.replace(/bootstrap\(\);/, '');
let runCount = 0;
const sandbox = {
  window: { __lastAnalyzed: '' },
  Word: {
    run: async (fn) => { runCount++; await fn({}); }
  }
};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
(async () => {
  await sandbox.applyOpsTracked([{start:5,end:3,replacement:'X'}]);
  console.log(JSON.stringify({runCount}));
})();
''')

def test_no_word_run_for_empty_ops(tmp_path):
    script = tmp_path / 'run.js'
    script.write_text(JS)
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip())
    assert data['runCount'] == 0
