import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('health positive', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('returns ok', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    const { checkHealth } = await import('../assets/health.ts');
    const res = await checkHealth({ backend: 'http://x' });
    expect(res.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const res2 = await checkHealth({ backend: 'http://x' });
    expect(res2.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
