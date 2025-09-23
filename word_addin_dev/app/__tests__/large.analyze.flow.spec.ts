import { describe, it, expect, vi } from 'vitest';

describe('large analyze flow', () => {
  it('extends timeout for large documents', async () => {
    vi.useFakeTimers();
    const timers: number[] = [];
    const origSet = setTimeout;
    (globalThis as any).setTimeout = ((fn: any, ms: number) => {
      timers.push(ms);
      return origSet(fn, ms);
    }) as any;
    const origClear = clearTimeout;
    (globalThis as any).clearTimeout = (id: any) => origClear(id);
    (globalThis as any).window = {
      dispatchEvent: () => {},
      addEventListener: () => {},
      location: { search: '' },
    } as any;
    (globalThis as any).location = (globalThis as any).window.location;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn(
      () =>
        new Promise(res =>
          setTimeout(
            () => res({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 }),
            12000
          )
        )
    );
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: 'a'.repeat(400 * 1024) });
    expect(timers[0]).toBeGreaterThan(9000);
    await vi.advanceTimersByTimeAsync(12000);
    await expect(p).resolves.toBeTruthy();
    vi.useRealTimers();
  });
});
