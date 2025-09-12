import { describe, it, expect, vi, beforeEach } from 'vitest';

const baseEnv = () => {
  (globalThis as any).window = globalThis;
  (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true }, host: 'Word' } } as any;
  (globalThis as any).Word = { Revision:{}, Comment:{}, SearchOptions:{}, ContentControl:{} } as any;
  (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
  (globalThis as any).__CAI_TESTING__ = true;
};

describe('startup selftest', () => {
  beforeEach(() => { vi.resetModules(); });

  it('fails when id missing', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: (id:string) => id==='btnAnalyze'? { setAttribute: () => {}, textContent: ''}: null, querySelector: () => null } as any;
    (globalThis as any).fetch = async () => ({ ok: true, json: async () => ({}), headers: new Headers(), status:200 });
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { runStartupSelftest } = await import('../assets/startup.selftest.ts');
    const res = await runStartupSelftest('https://x');
    expect(res.ok).toBe(false);
    expect(log).toHaveBeenCalledWith(expect.stringMatching(/^Startup FAIL:/));
  });

  it('fails when health fails', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: () => ({ setAttribute: () => {}, textContent: '' }) , querySelector: () => null } as any;
    (globalThis as any).fetch = vi.fn().mockRejectedValue(new Error('fail'));
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { runStartupSelftest } = await import('../assets/startup.selftest.ts');
    const res = await runStartupSelftest('https://x');
    expect(res.ok).toBe(false);
    expect(log).toHaveBeenCalledWith(expect.stringMatching(/^Startup FAIL:/));
  });

  it('passes on happy path', async () => {
    baseEnv();
    (globalThis as any).document = { getElementById: () => ({ setAttribute: () => {}, textContent: '' }) , querySelector: () => null } as any;
    (globalThis as any).fetch = async () => ({ ok: true, json: async () => ({}) , headers: new Headers(), status:200 });
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { runStartupSelftest } = await import('../assets/startup.selftest.ts');
    const res = await runStartupSelftest('https://x');
    expect(res.ok).toBe(true);
    expect(log).toHaveBeenCalledWith(expect.stringMatching(/^Startup OK \| build=.*\| host=Word \| req=1\.4 \| features=\{.*\} \| backend=https:\/\/x$/));
  });
});
