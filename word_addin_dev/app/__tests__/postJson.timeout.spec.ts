import { describe, it, expect } from 'vitest';

describe('postJson timeout', () => {
  it('aborts on timeout', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = (_:any, opts:any) => new Promise((_res, rej) => {
      opts.signal.addEventListener('abort', () => rej(new DOMException('aborted','AbortError')));
    });
    const { postJson } = await import('../assets/api-client.ts');
    await expect(postJson('/x', {}, 5)).rejects.toThrow();
  });

  it('health check times out', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = (_:any, opts:any) => new Promise((_res, rej) => {
      opts.signal.addEventListener('abort', () => rej(new DOMException('aborted','AbortError')));
    });
    const { checkHealth } = await import('../assets/health.ts');
    await expect(checkHealth({ timeoutMs: 5 })).rejects.toThrow();
  });
});
