const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const elements = {
  backendInput: { value: 'https://localhost:9443', textContent:'', style:{}, className:'', addEventListener: () => {} },
  apiKeyInput: { value: 'KEY123', textContent:'', style:{}, className:'', addEventListener: () => {} },
  schemaInput: { value: '1.0', textContent:'', style:{}, className:'', addEventListener: () => {} },
  cidLbl: { textContent:'', style:{}, className:'', addEventListener: () => {} },
  lastCidLbl: { textContent:'', style:{}, className:'', addEventListener: () => {} },
  resp: { textContent:'', style:{}, className:'', addEventListener: () => {} }
};

const sandbox = {
  console,
  alert: () => {},
  document: {
    getElementById: id => elements[id] || { value:'', textContent:'', style:{}, className:'', addEventListener: () => {} },
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

let code;

// minimal CAI.Store stub
const storeState = { lastCid:null, schemaVersion:'', apiKey:'' };
sandbox.CAI = { Store: {
  setBase: () => {},
  setApiKey: k => { storeState.apiKey = k; },
  setSchemaVersion: v => { storeState.schemaVersion = v; },
  setMeta: m => { if (m.cid) storeState.lastCid = m.cid; if (m.schema) storeState.schemaVersion = m.schema; },
  get: () => ({ ...storeState })
}};

// stub fetch for both health and analyze
sandbox._lastReq = {};
sandbox.fetch = async (url, opts = {}) => {
  if (url.endsWith('/health')) {
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
  }
  if (url.endsWith('/api/analyze')) {
    sandbox._lastReq = { url, opts };
    const headers = new Map([
      ['x-cid', 'cid-a'],
      ['x-schema-version', '1.1'],
    ]);
    return {
      ok: true,
      status: 200,
      headers: { get: k => headers.get(k) },
      json: async () => ({ status: 'ok' })
    };
  }
  throw new Error('Unexpected fetch url: ' + url);
};

// load api-client to provide postJson
code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/assets/api-client.js', 'utf8');
code = code.replace(/export\s+\{[\s\S]*?\};?/g, '');
vm.runInNewContext(code, sandbox);

// load selftest.js which uses postJson
code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/selftest.js', 'utf8');
vm.runInNewContext(code, sandbox);

(async () => {
  const rHealth = await sandbox.callEndpoint({ name:'health', method:'GET', path:'/health' });
  assert.strictEqual(rHealth.code, 200);
  assert.strictEqual(rHealth.xcid, 'cid-h');
  assert.strictEqual(rHealth.xschema, '1.0');

  // with explicit headers provided
  let rAnalyze = await sandbox.callEndpoint({ name:'analyze', method:'POST', path:'/api/analyze', body:{text:'hi'} });
  assert.strictEqual(rAnalyze.code, 200);
  assert.strictEqual(rAnalyze.xcid, 'cid-a');
  let sent = sandbox._lastReq;
  assert.deepStrictEqual(JSON.parse(sent.opts.body), { text: 'hi' });
  assert.strictEqual(sent.opts.headers['content-type'], 'application/json');
  assert.strictEqual(sent.opts.headers['x-api-key'], 'KEY123');
  assert.strictEqual(sent.opts.headers['x-schema-version'], '1.0');
  assert.strictEqual(sandbox.CAI.Store.get().lastCid, 'cid-a');

  // without headers in inputs or storage
  elements.apiKeyInput.value = '';
  elements.schemaInput.value = '';
  sandbox.localStorage._data = {};
  storeState.apiKey = '';
  storeState.schemaVersion = '';
  rAnalyze = await sandbox.callEndpoint({ name:'analyze', method:'POST', path:'/api/analyze', body:{text:'bye'} });
  assert.strictEqual(rAnalyze.code, 200);
  sent = sandbox._lastReq;
  assert.deepStrictEqual(JSON.parse(sent.opts.body), { text: 'bye' });
  assert.strictEqual(sent.opts.headers['x-api-key'], undefined);
  assert.strictEqual(sent.opts.headers['x-schema-version'], undefined);

  console.log('selftest call tests ok');
})();

