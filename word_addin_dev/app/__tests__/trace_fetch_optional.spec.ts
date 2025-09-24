import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

describe('trace fetch optional', () => {
  const localStorageStub = {
    getItem: vi.fn().mockReturnValue(null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  } as any;

  beforeEach(() => {
    vi.restoreAllMocks();
    const winStub: any = {
      __cai_pending_fetches: new Set(),
      __cai_pending_timers: new Set(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      location: { search: '' },
      document: { addEventListener: vi.fn(), removeEventListener: vi.fn() },
    };
    vi.stubGlobal('window', winStub);
    vi.stubGlobal('document', winStub.document);
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (globalThis as any).window;
    delete (globalThis as any).document;
    delete (globalThis as any).localStorage;
    delete (globalThis as any).fetch;
    vi.resetModules();
  });

  it('returns parsed trace when backend responds with 200', async () => {
    const payload = { trace: true };
    const jsonMock = vi.fn().mockResolvedValue(payload);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: jsonMock });
    vi.stubGlobal('fetch', fetchMock as any);

    const { getTrace } = await import('../assets/api-client.ts');

    const result = await getTrace('cid-123');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain('/api/trace/cid-123');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' });
    expect(result).toEqual(payload);
  });

  it('returns undefined when backend responds with non-OK status', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, json: vi.fn() });
    vi.stubGlobal('fetch', fetchMock as any);

    const { getTrace } = await import('../assets/api-client.ts');
    const result = await getTrace('cid-404');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result).toBeUndefined();
  });

  it('returns undefined when request fails', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('network'));
    vi.stubGlobal('fetch', fetchMock as any);

    const { getTrace } = await import('../assets/api-client.ts');
    const result = await getTrace('cid-error');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result).toBeUndefined();
  });
});
