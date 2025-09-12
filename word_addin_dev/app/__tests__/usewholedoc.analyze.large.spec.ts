import { describe, it, expect, vi } from 'vitest';

describe('analyze large logging', () => {
  it('logs size and duration', async () => {
    vi.useFakeTimers();
    (globalThis as any).window = { dispatchEvent: () => {}, addEventListener: () => {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const longText = 'A'.repeat(120000);
    const fetchMock = vi.fn(() =>
      new Promise(res => setTimeout(() => res({ ok:true, json: async()=>({}), headers:new Headers(), status:200 }), 12000))
    );
    (globalThis as any).fetch = fetchMock;
    const logSpy = vi.spyOn(console, 'log');
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: longText });
    await vi.advanceTimersByTimeAsync(12000);
    await p;
    const size = new TextEncoder().encode(longText).length;
    const rec = logSpy.mock.calls.find(c => c[0] === 'analyze');
    expect(rec?.[1].size_bytes).toBe(size);
    expect(rec?.[1].t_ms).toBeGreaterThanOrEqual(11000);
    vi.useRealTimers();
  });
});
