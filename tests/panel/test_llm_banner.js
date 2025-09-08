const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const elements = {
  llmProv: { textContent: '' },
  llmModel: { textContent: '' },
  llmLatency: { textContent: '', className: '' },
  llmBadge: { style: { display: 'none' } },
  backendInput: { value: 'https://localhost:9443' },
  apiKeyInput: { value: '' },
  cidLbl: { textContent: '' },
  lastCidLbl: { textContent: '' },
  resp: { textContent: '' },
};

const calls = [];

const sandbox = {
  console,
  alert: () => {},
  document: {
    getElementById: id => elements[id] || { textContent: '', style: {}, className: '', addEventListener: () => {} },
    querySelector: () => ({})
  },
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  addEventListener: (ev, fn) => { if (ev === 'DOMContentLoaded') sandbox._dom = fn; },
  CAI: {
    API: {
      get: async path => {
        calls.push(path);
        if (path === '/health') {
          return {
            ok: true,
            json: { status: 'ok', llm: { provider: 'mock', models: { draft: 'mock-static' }, mode: 'mock' } },
            resp: { status: 200, headers: { get: () => null } },
            meta: {}
          };
        }
        if (path === '/api/llm/ping') {
          return {
            ok: true,
            json: { status: 'ok' },
            resp: { status: 200, headers: { get: k => (k === 'x-latency-ms' ? '7' : null) } },
            meta: { latencyMs: 7 }
          };
        }
        throw new Error('unexpected path ' + path);
      }
    },
    Store: { setBase: () => {}, get: () => ({}) }
  }
};

sandbox.window = sandbox; sandbox.self = sandbox;

const code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/selftest.js', 'utf8');
vm.runInNewContext(code, sandbox);

// Stub openapi loader to avoid network
sandbox.loadOpenAPI = async () => ({});
sandbox.buildRowsFromOpenAPI = () => {};

(async () => {
  await sandbox._dom();
  assert.strictEqual(calls[0], '/health');
  assert.strictEqual(elements.llmProv.textContent, 'mock');
  assert.strictEqual(elements.llmModel.textContent, 'mock-static');
  assert.strictEqual(elements.llmLatency.textContent, 'mock');
  assert.strictEqual(elements.llmLatency.className, 'ok');
  await sandbox.pingLLM();
  assert.ok(calls.includes('/api/llm/ping'));
  assert.strictEqual(elements.llmLatency.textContent, '7ms');
  assert.strictEqual(elements.llmLatency.className, 'ok');
  console.log('llm banner tests ok');
})();
