const assert = require('assert');

function parseFindings(resp){
  const arr = (resp && (
      (resp.analysis && resp.analysis.findings) ||
      resp.findings ||
      resp.issues ||
      []
  )) || [];
  return Array.isArray(arr) ? arr.filter(Boolean) : [];
}

describe('parseFindings', () => {
  it('reads from analysis.findings', () => {
    const out = parseFindings({ analysis: { findings: [{ rule_id: 'r1' }] } });
    assert.equal(out.length, 1);
  });
  it('fallback to findings', () => {
    const out = parseFindings({ findings: [{ rule_id: 'r2' }] });
    assert.equal(out.length, 1);
  });
  it('fallback to issues', () => {
    const out = parseFindings({ issues: [{ rule_id: 'r3' }] });
    assert.equal(out.length, 1);
  });
  it('empty otherwise', () => {
    const out = parseFindings({});
    assert.equal(out.length, 0);
  });
});

