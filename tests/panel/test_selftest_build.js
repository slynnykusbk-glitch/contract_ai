const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/selftest.js', 'utf8');

const btns = { html:'', insertAdjacentHTML(pos, html){ this.html += html; } };
const body = { html:'', insertAdjacentHTML(pos, html){ this.html += html; } };

const sandbox = {
  console,
  alert: () => {},
  onClick: () => {},
  runGeneric: () => {},
  document: {
    getElementById: (id) => {
      if (id === 'testsBtns') return btns;
      if (id === 'statusBody') return body;
      return { addEventListener: () => {}, getElementsByTagName: () => [], style:{}, value:'', textContent:'' };
    },
    querySelector: () => ({})
  },
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  CAI: { API:{}, Store:{ setBase:()=>{}, get:()=>({}) } },
  addEventListener: () => {}
};

sandbox.window = sandbox; sandbox.self = sandbox;
vm.runInNewContext(code, sandbox);

const paths = {
  '/api/analyze': { post: {} },
  '/api/gpt-draft': { post: {} },
  '/api/trace/{cid}': { get: {} }
};

sandbox.buildRowsFromOpenAPI(paths);

const btnCount = (btns.html.match(/<button/g) || []).length;
const rowCount = (body.html.match(/<tr/g) || []).length;
assert.strictEqual(btnCount, 3);
assert.strictEqual(rowCount, 3);
assert.ok(btns.html.includes('POST /api/analyze'));
assert.ok(btns.html.includes('POST /api/gpt-draft'));
assert.ok(btns.html.includes('GET /api/trace'));
assert.ok(!btns.html.includes('qa-recheck'));

console.log('selftest build tests ok');
