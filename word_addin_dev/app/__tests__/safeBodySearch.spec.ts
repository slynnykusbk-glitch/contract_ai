import { describe, it, expect, vi } from 'vitest';
import { safeBodySearch } from '../assets/safe-search.ts';

describe('safeBodySearch', () => {
  it('handles SearchStringInvalidOrTooLong gracefully', () => {
    const body = {
      search: vi.fn().mockImplementation(() => { const err: any = new Error('fail'); err.code = 'SearchStringInvalidOrTooLong'; throw err; }),
    };
    const res = safeBodySearch(body, 'x', {});
    expect(res.items.length).toBe(0);
    expect(body.search).toHaveBeenCalledOnce();
  });

  it('truncates long strings', () => {
    const long = 'a'.repeat(5000);
    const body = { search: vi.fn().mockReturnValue({ items: [] }) };
    safeBodySearch(body, long, {});
    const arg = body.search.mock.calls[0][0];
    expect(arg.length).toBeLessThanOrEqual(200);
  });

  it('passes short strings through', () => {
    const body = { search: vi.fn().mockReturnValue({ items: [1] }) };
    const res = safeBodySearch(body, 'short', {});
    expect(res.items[0]).toBe(1);
    expect(body.search).toHaveBeenCalledWith('short', {});
  });
});
