import { describe, it, expect, vi } from 'vitest';

describe('postJson timeout/retry', () => {
  it('aborts after computed timeout and retries', async () => {
    vi.useFakeTimers();
    const timers: number[] = [];
    const origSet = setTimeout;
    (globalThis as any).setTimeout = ((fn: any, ms: number) => { timers.push(ms); return origSet(fn, ms); }) as any;
    const origClear = clearTimeout;
    (globalThis as any).clearTimeout = (id: any) => origClear(id);
    (globalThis as any).window = { dispatchEvent: () => {}, addEventListener: () => {}, location: { search: '' } } as any;
    (globalThis as any).location = (globalThis as any).window.location;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const logs: string[] = [];
    vi.spyOn(console, 'log').mockImplementation((...a: any[]) => { logs.push(a.join(' ')); });
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_u, opts: any) => new Promise((_res, rej) => {
        opts.signal.addEventListener('abort', () => rej(new DOMException('x', 'AbortError')));
      }))
      .mockResolvedValueOnce({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: 'hi' });
    const timeout = timers[0];
    await vi.advanceTimersByTimeAsync(timeout);
    const backoff = timers[1];
    await vi.advanceTimersByTimeAsync(backoff + 1);
    await expect(p).resolves.toBeTruthy();
    expect(fetchMock.mock.calls.length).toBe(2);
    expect(logs.find(l => l.includes('timeout'))).toContain(String(timeout));
    vi.useRealTimers();
  }, 20000);

  it('overrides via localStorage and query params', async () => {
    vi.useFakeTimers();
    const timers: number[] = [];
    const origSet = setTimeout;
    (globalThis as any).setTimeout = ((fn: any, ms: number) => { timers.push(ms); return origSet(fn, ms); }) as any;
    const origClear2 = clearTimeout;
    (globalThis as any).clearTimeout = (id: any) => origClear2(id);
    const store: Record<string, string> = {
      'cai.timeout.analyze.ms': '15000',
      'cai.retry.analyze.count': '1',
      'cai.retry.analyze.backoff.ms': '2000',
    };
    (globalThis as any).localStorage = {
      getItem: (k: string) => store[k] || null,
      setItem: (k: string, v: string) => { store[k] = v; },
    } as any;
    (globalThis as any).window = {
      dispatchEvent: () => {},
      addEventListener: () => {},
      location: { search: '?ta=40000&rac=2&rb=5000' },
    } as any;
    (globalThis as any).location = (globalThis as any).window.location;
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_u, opts: any) => new Promise((_res, rej) => {
        opts.signal.addEventListener('abort', () => rej(new DOMException('x', 'AbortError')));
      }))
      .mockImplementationOnce((_u, opts: any) => new Promise((_res, rej) => {
        opts.signal.addEventListener('abort', () => rej(new DOMException('x', 'AbortError')));
      }))
      .mockResolvedValueOnce({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: 'hi' });
    const timeout1 = timers[0];
    await vi.advanceTimersByTimeAsync(timeout1);
    const backoff1 = timers[1];
    await vi.advanceTimersByTimeAsync(backoff1);
    const timeout2 = timers[2];
    await vi.advanceTimersByTimeAsync(timeout2);
    const backoff2 = timers[3];
    await vi.advanceTimersByTimeAsync(backoff2 + 1);
    await expect(p).resolves.toBeTruthy();
    expect(fetchMock.mock.calls.length).toBe(3);
    expect(timeout1).toBe(40000);
    expect(backoff1).toBe(5000);
    vi.useRealTimers();
  }, 40000);
});
