const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/selftest.js', 'utf8');

const sandbox = {
  console,
  alert: () => {},
  fetch: async (url, opts = {}) => {
    // health endpoint should not send x-api-key
    assert.ok(url.endsWith('/health'));
    assert.ok(!opts.headers || !('x-api-key' in opts.headers));
    const headers = new Map([
      ['x-cid', 'cid-h'],
      ['x-schema-version', '1.0'],
      ['x-latency-ms', '42']
    ]);
    return {
      ok: true,
      status: 200,
      headers: { get: k => headers.get(k) },
      json: async () => ({ status: 'ok', llm:{provider:'p',model:'m',mode:'mock'} })
    };
  },
  CAI: {
    API: {
      analyze: async (text) => {
        assert.strictEqual(sandbox.localStorage.getItem('api_key'), 'KEY123');
        const headers = new Map([
          ['x-cid', 'cid-a'],
          ['x-schema-version', '1.1'],
          ['x-latency-ms', '7']
        ]);
        return { ok:true, resp:{ status:200, headers:{ get: k => headers.get(k) } }, json:{ status:'ok', meta:{} } };
      }
    },
    Store: { setBase: () => {}, get: () => ({}) }
  },
  document: {
    getElementById: (id) => {
      const el = { value: '', textContent: '', style:{}, className:'', addEventListener: () => {} };
      if (id === 'backendInput') el.value = 'https://localhost:9443';
      if (id === 'apiKeyInput') el.value = 'KEY123';
      return el;
    },
    querySelector: () => ({})
  },
  localStorage: {
    _data: { 'api_key': 'OLD' },
    getItem(k){ return this._data[k] || null; },
    setItem(k,v){ this._data[k] = String(v); },
    removeItem(k){ delete this._data[k]; }
  },
  addEventListener: () => {}
};
sandbox.window = sandbox; sandbox.self = sandbox;

vm.runInNewContext(code, sandbox);

(async () => {
  const rHealth = await sandbox.callEndpoint({ name:'health', method:'GET', path:'/health' });
  assert.strictEqual(rHealth.code, 200);
  assert.strictEqual(rHealth.xcid, 'cid-h');
  assert.strictEqual(rHealth.xschema, '1.0');
  const rAnalyze = await sandbox.callEndpoint({ name:'analyze', method:'POST', path:'/api/analyze', body:{text:'hi'} });
  assert.strictEqual(rAnalyze.code, 200);
  assert.strictEqual(rAnalyze.xcid, 'cid-a');
  console.log('selftest call tests ok');
})();
