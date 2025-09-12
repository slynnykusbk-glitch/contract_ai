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
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/api/analyze', { text: longText });
    await vi.advanceTimersByTimeAsync(12000);
    await expect(p).resolves.toBeTruthy();
    vi.useRealTimers();
  });
});
