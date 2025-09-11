import { describe, it, expect, vi, beforeEach } from 'vitest';

const baseEnv = () => {
  (globalThis as any).window = globalThis;
  (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
  (globalThis as any).Word = { Revision:{}, Comment:{}, SearchOptions:{}, ContentControl:{} } as any;
  (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
  (globalThis as any).__CAI_TESTING__ = true;
};

describe('startup selftest', () => {
  beforeEach(() => { vi.resetModules(); });
  it('fails when id missing', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: (id:string) => id==='btnAnalyze'? { setAttribute: () => {}, textContent: '' }: null, querySelector: () => null } as any;
    (globalThis as any).fetch = async () => ({ ok: true, json: async () => ({}) , headers: new Headers(), status:200 });
    const { runStartupSelftest } = await import('../assets/taskpane.ts');
    const res = await runStartupSelftest();
    expect(res.ok).toBe(false);
  });

  it('fails when health fails', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: () => ({ setAttribute: () => {}, textContent: '' }) , querySelector: () => null } as any;
    (globalThis as any).fetch = async () => { throw new Error('fail'); };
    const { runStartupSelftest } = await import('../assets/taskpane.ts');
    const res = await runStartupSelftest();
    expect(res.ok).toBe(false);
  });

  it('passes on happy path', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: () => ({ setAttribute: () => {}, textContent: '' }) , querySelector: () => null } as any;
    (globalThis as any).fetch = async () => ({ ok: true, json: async () => ({}) , headers: new Headers(), status:200 });
    const { runStartupSelftest } = await import('../assets/taskpane.ts');
    const res = await runStartupSelftest();
    expect(res.ok).toBe(true);
  });
});
