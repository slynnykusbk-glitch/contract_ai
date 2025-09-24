import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const setupDom = () => {
  (globalThis as any).window = {
    addEventListener() {},
    dispatchEvent() {},
    location: { search: '' },
  } as any;
  (globalThis as any).document = {
    addEventListener() {},
    querySelectorAll() { return [] as any; },
  } as any;
  const store = new Map<string, string>();
  (globalThis as any).localStorage = {
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
  (globalThis as any).localStorage.setItem('cai.retry.analyze.count', '0');
};

const teardownDom = () => {
  delete (globalThis as any).fetch;
  delete (globalThis as any).localStorage;
  delete (globalThis as any).window;
  delete (globalThis as any).document;
};

const mockFetchWithAbort = () =>
  vi.fn((_url, opts: any) => new Promise((_resolve, reject) => {
    opts?.signal?.addEventListener?.('abort', () => {
      reject(new DOMException('Aborted', 'AbortError'));
    });
  }));

describe('analyze timeout behaviour', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setupDom();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.resetModules();
    vi.restoreAllMocks();
    teardownDom();
  });

  it('aborts around 28s when no text bytes are known', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');
    const fetchMock = mockFetchWithAbort();
    (globalThis as any).fetch = fetchMock;
    const { analyze, computeAnalyzeTimeout } = await import('../api-client.ts');

    const promise = analyze({ text: '' }).catch(() => undefined);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const expectedTimeout = computeAnalyzeTimeout(0);
    await vi.advanceTimersByTimeAsync(expectedTimeout - 1);
    expect(abortSpy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(abortSpy).toHaveBeenCalledWith(`timeout ${expectedTimeout}ms`);
    await expect(promise).resolves.toBeUndefined();
    abortSpy.mockRestore();
  });

  it('scales timeout with large texts but caps at ceiling', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');
    const fetchMock = mockFetchWithAbort();
    (globalThis as any).fetch = fetchMock;
    const { analyze, computeAnalyzeTimeout } = await import('../api-client.ts');
    const hugeText = 'x'.repeat(600 * 1024);
    (globalThis as any).window.__lastAnalyzed = { text: hugeText };

    const promise = analyze({ text: '' }).catch(() => undefined);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const expectedTimeout = computeAnalyzeTimeout(600 * 1024);
    expect(expectedTimeout).toBeGreaterThan(28_000);
    expect(expectedTimeout).toBeLessThanOrEqual(120_000);
    await vi.advanceTimersByTimeAsync(expectedTimeout - 1);
    expect(abortSpy).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(abortSpy).toHaveBeenCalledWith(`timeout ${expectedTimeout}ms`);
    await expect(promise).resolves.toBeUndefined();
    abortSpy.mockRestore();
  });
});
