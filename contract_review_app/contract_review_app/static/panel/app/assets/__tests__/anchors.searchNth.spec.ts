import { describe, it, expect, vi, beforeEach } from 'vitest';

let searchNth: (typeof import('../anchors'))['searchNth'];

beforeEach(async () => {
  vi.resetModules();
  const mod = await import('../anchors');
  searchNth = mod.searchNth;
});

describe('searchNth', () => {
  it('returns i-th range when nth = i', async () => {
    const items = [
      { id: 'a' },
      { id: 'b' },
      { id: 'c' }
    ];
    const load = vi.fn();
    const body = {
      context: { sync: vi.fn(async () => {}) },
      search: vi.fn(() => ({ items, load }))
    } as any;

    const range = await searchNth(body, 'needle', 2);
    expect(body.search).toHaveBeenCalledWith('needle', { matchCase: false, matchWholeWord: false });
    expect(range).toBe(items[2]);
  });

  it('returns null when nth exceeds available matches', async () => {
    const items = [{ id: 'only' }];
    const body = {
      context: { sync: vi.fn(async () => {}) },
      search: vi.fn(() => ({ items, load: vi.fn() }))
    } as any;

    const range = await searchNth(body, 'needle', 5);
    expect(range).toBeNull();
  });
});
