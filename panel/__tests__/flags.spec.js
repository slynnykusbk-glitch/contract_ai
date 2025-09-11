require('ts-node/register');

describe('Add comments flag', () => {
  let mod;
  beforeEach(() => {
    global.window = {};
    global.document = { getElementById: () => ({ style: {}, addEventListener: () => {} }), querySelector: () => null, addEventListener: () => {}, body: { dispatchEvent() {} } };
    global.localStorage = {
      store: {},
      getItem(k) { return this.store[k] ?? null; },
      setItem(k, v) { this.store[k] = v; },
      removeItem(k) { delete this.store[k]; }
    };
    mod = require('../../word_addin_dev/app/assets/taskpane.js');
  });

  it('defaults to true when missing', () => {
    expect(mod.isAddCommentsOnAnalyzeEnabled()).toBe(true);
  });

  it('persists value', () => {
    mod.setAddCommentsOnAnalyze(false);
    expect(mod.isAddCommentsOnAnalyzeEnabled()).toBe(false);
  });
});
