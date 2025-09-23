import { describe, it, expect, vi } from 'vitest';
import { safeBodySearch } from '../assets/safeBodySearch.ts';

describe('safeBodySearch', () => {
  it('returns empty items when search keeps failing', async () => {
    const body: any = {
      context: { sync: vi.fn() },
      search: vi.fn().mockImplementation(() => {
        const err: any = new Error('fail');
        err.code = 'SearchStringInvalidOrTooLong';
        throw err;
      }),
    };
    const res = await safeBodySearch(body, 'x'.repeat(500), {});
    expect(res.items.length).toBe(0);
    expect(body.search).toHaveBeenCalled();
  });

  it('returns result when search succeeds after truncation', async () => {
    const inner = {
      text: 'a'.repeat(500),
      search: vi.fn().mockReturnValue({ items: [1], load: vi.fn() }),
    };
    const scope = { paragraphs: { getFirst: vi.fn().mockReturnValue(inner) } };
    const body: any = {
      context: { sync: vi.fn() },
      search: vi.fn().mockImplementation((txt: string) => {
        if (txt.length > 200) {
          const err: any = new Error('fail');
          err.code = 'SearchStringInvalidOrTooLong';
          throw err;
        }
        return { items: [scope], load: vi.fn() };
      }),
    };
    const res = await safeBodySearch(body, 'a'.repeat(500), {});
    expect(res.items[0]).toBe(1);
    expect(body.search).toHaveBeenCalled();
  });
});
