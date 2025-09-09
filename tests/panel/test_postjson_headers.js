const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const sandbox = {
  console,
  localStorage: {
    _data: {},
    getItem(k){ return this._data[k] || null; },
    setItem(k,v){ this._data[k] = String(v); },
    removeItem(k){ delete this._data[k]; }
  },
};
sandbox.window = sandbox;

const storeState = { apiKey: '', meta: null };
sandbox.CAI = { Store: {
  setApiKey: k => { storeState.apiKey = k; },
  setMeta: m => { storeState.meta = m; },
}};

let lastReq;
sandbox.fetch = async (url, opts = {}) => {
  lastReq = opts;
  return { json: async () => ({}), headers: { get: () => null }, status: 200 };
};

let code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/assets/api-client.js', 'utf8');
code = code.replace(/export\s+\{[\s\S]*?\};?/g, '');
vm.runInNewContext(code, sandbox);

(async () => {
  sandbox.localStorage._data = { 'api_key': 'KEY_LS', 'schemaVersion': '1.2' };
  await sandbox.postJson('/test', { a: 1 });
  assert.strictEqual(lastReq.headers['x-api-key'], 'KEY_LS');
  assert.strictEqual(lastReq.headers['x-schema-version'], '1.2');

  sandbox.localStorage._data = {};
  await sandbox.postJson('/test', { a: 1 });
  assert.ok(!('x-api-key' in lastReq.headers));
  assert.ok(!('x-schema-version' in lastReq.headers));

  await sandbox.postJson('/test', { a: 1 }, { apiKey: 'OVERRIDE', schemaVersion: '3.0' });
  assert.strictEqual(lastReq.headers['x-api-key'], 'OVERRIDE');
  assert.strictEqual(lastReq.headers['x-schema-version'], '3.0');
  assert.strictEqual(sandbox.localStorage.getItem('api_key'), 'OVERRIDE');
  assert.strictEqual(storeState.apiKey, 'OVERRIDE');

  console.log('postJson header tests ok');
})();
