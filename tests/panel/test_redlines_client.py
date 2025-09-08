import json
import subprocess
from pathlib import Path


def test_redlines_client_sends_two_fields():
    api_path = Path(__file__).resolve().parents[2] / 'word_addin_dev' / 'app' / 'assets' / 'api-client.js'
    script = f"""
    global.window = {{}};
    const mod = await import('file://{api_path.as_posix()}');
    const calls = [];
    global.window.postJson = (url, body) => {{ calls.push([url, body]); return Promise.resolve({{}}); }};
    await mod.postRedlines('a', 'b');
    console.log(JSON.stringify(calls));
    """
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, check=True)
    calls = json.loads(result.stdout.strip())
    assert calls == [["/api/panel/redlines", {"before_text": "a", "after_text": "b"}]]
