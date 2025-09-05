const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let code = fs.readFileSync(__dirname + '/../../word_addin_dev/app/assets/api-client.js', 'utf8');
// Strip ESM exports for vm execution
code = code.replace(/export\s+/g, '');
const sandbox = { console };
vm.runInNewContext(code, sandbox);
const parseFindings = sandbox.parseFindings;

const sample = { rule_id: 'r1', clause_type: 'c', severity: 's', start: 0, end: 1, snippet: 'x' };
assert.deepStrictEqual(parseFindings({ analysis: { findings: [sample] } }).length, 1);
assert.deepStrictEqual(parseFindings({ findings: [sample] }).length, 1);
assert.deepStrictEqual(parseFindings({ issues: [sample] }).length, 1);
assert.deepStrictEqual(parseFindings({ analysis: { findings: null } }).length, 0);
console.log('parseFindings tests ok');
