require('ts-node/register');
const { isAddCommentsOnAnalyzeEnabled, setAddCommentsOnAnalyze } = require('../../word_addin_dev/app/assets/taskpane');

describe('Add comments flag', () => {
  beforeEach(() => {
    const g = global;
    g.localStorage = {
      store: {},
      getItem(k) { return this.store[k] ?? null; },
      setItem(k, v) { this.store[k] = v; },
      removeItem(k) { delete this.store[k]; }
    };
  });

  it('defaults to true when missing', () => {
    expect(isAddCommentsOnAnalyzeEnabled()).toBe(true);
  });

  it('persists value', () => {
    setAddCommentsOnAnalyze(false);
    expect(isAddCommentsOnAnalyzeEnabled()).toBe(false);
  });
});
