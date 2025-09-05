const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/assets/store.js', 'utf8');
code = code.replace(/export\s+/g, '');
const globalCAI = {};
const sandbox = {
  window: { CAI: globalCAI },
  CAI: globalCAI,
  localStorage: {
    _data: {},
    getItem(k){ return this._data[k] || null; },
    setItem(k,v){ this._data[k] = String(v); }
  }
};
sandbox.self = sandbox.window;
vm.runInNewContext(code, sandbox);

const store = sandbox.window.CAI.store;

// Initial empty
assert.deepStrictEqual(store.get('cai:suggestions', []), []);

// Apply
store.set('cai:suggestions', [{id:'1', status:'pending'}]);
store.updateSuggestion('1', {status:'applied'});
assert.strictEqual(store.get('cai:suggestions', [])[0].status, 'applied');

// Accept
store.updateSuggestion('1', {status:'accepted'});
assert.strictEqual(store.get('cai:suggestions', [])[0].status, 'accepted');

// Reject
store.updateSuggestion('1', {status:'rejected'});
assert.strictEqual(store.get('cai:suggestions', [])[0].status, 'rejected');

console.log('store tests ok');

