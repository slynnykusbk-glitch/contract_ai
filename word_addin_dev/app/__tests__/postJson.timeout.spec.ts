import { describe, it, expect, vi } from 'vitest';

describe('postJson timeout', () => {
  it('uses dynamic timeout for small text', async () => {
    (globalThis as any).window = { dispatchEvent: () => {}, addEventListener: () => {} } as any;
    const calls: number[] = [];
    (globalThis as any).setTimeout = (fn: any, ms: number) => { calls.push(ms); return 0 as any; };
    (globalThis as any).clearTimeout = () => {};
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status:200 });
    const { postJson } = await import('../assets/api-client.ts');
    await postJson('/api/analyze', { text: 'hi' });
    expect(calls[0]).toBeGreaterThanOrEqual(9000);
    expect(calls[0]).toBeLessThanOrEqual(30000);
  });

  it('large text uses 60s and resolves before abort', async () => {
    vi.useFakeTimers();
    (globalThis as any).window = { dispatchEvent: () => {}, addEventListener: () => {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn(() =>
      new Promise(res => setTimeout(() => res({ ok:true, json: async()=>({}), headers:new Headers(), status:200 }), 12000))
    );
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: 'a'.repeat(120000) });
    await vi.advanceTimersByTimeAsync(12000);
    await expect(p).resolves.toBeTruthy();
    vi.useRealTimers();
  });

  it('retries once on timeout', async () => {
    vi.useFakeTimers();
    (globalThis as any).window = { dispatchEvent: () => {}, addEventListener: () => {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const timers: number[] = [];
    const origSet = setTimeout;
    (globalThis as any).setTimeout = ((fn: any, ms: number) => { timers.push(ms); return origSet(fn, ms); }) as any;
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_u, opts:any) => new Promise((_res, rej) => {
        opts.signal.addEventListener('abort', () => rej(new DOMException('x','AbortError')));
      }))
      .mockResolvedValueOnce({ ok:true, json: async()=>({}), headers:new Headers(), status:200 });
    ;(globalThis as any).fetch = fetchMock;
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: 'hi' });
    await vi.advanceTimersByTimeAsync(30000);
    await expect(p).resolves.toBeTruthy();
    expect(fetchMock.mock.calls.length).toBe(2);
    expect(timers[0]).toBe(30000);
    expect(timers[1]).toBe(60000);
    vi.useRealTimers();
  });
});
