import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { detectSupports } from '../supports.ts';

describe('comments support detection', () => {
  const store: Record<string, string> = {};
  beforeEach(() => {
    (globalThis as any).localStorage = {
      getItem: (k: string) => (k in store ? store[k] : null),
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
    };
  });
  afterEach(() => {
    for (const k of Object.keys(store)) delete store[k];
    delete (globalThis as any).Word;
    delete (globalThis as any).Office;
  });

  it('uses Word.Comment when requirement set is unsupported', () => {
    (globalThis as any).Word = { Comment: function() {} };
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };
    expect(detectSupports().comments).toBe(true);
  });

  it('respects localStorage override', () => {
    (globalThis as any).localStorage.setItem('cai.force.comments', '1');
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };
    expect(detectSupports().comments).toBe(true);
  });

  it('returns false when no support and no override', () => {
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };
    expect(detectSupports().comments).toBe(false);
  });
});
