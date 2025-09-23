import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const safeBodySearchMock = vi.fn();

vi.mock('../assets/safeBodySearch.ts', async () => {
  const actual = await vi.importActual<typeof import('../assets/safeBodySearch.ts')>(
    '../assets/safeBodySearch.ts'
  );
  return {
    ...actual,
    safeBodySearch: safeBodySearchMock,
  };
});

describe('anchorByOffsets behaviour', () => {
  const makeBody = () => ({
    context: {
      sync: vi.fn(async () => {}),
      trackedObjects: { add: vi.fn() },
    },
  });

  beforeEach(() => {
    safeBodySearchMock.mockReset();
  });

  afterEach(() => {
    delete (globalThis as any).__cfg_anchorOffsets;
  });

  it('prefers the closest range when offsets are provided', async () => {
    const { anchorByOffsets } = await import('../assets/anchors');
    const body = makeBody();
    const target = { start: 42, end: 50 };
    const far = { start: 420, end: 428 };

    safeBodySearchMock.mockResolvedValueOnce({ items: [far, target] });

    const onMethod = vi.fn();
    const range = await anchorByOffsets({
      body: body as any,
      snippet: 'Sample text',
      start: 42,
      end: 50,
      nth: 0,
      searchOptions: { matchCase: false, matchWholeWord: false },
      onMethod,
    });

    expect(range).toBe(target);
    expect(onMethod).toHaveBeenCalledWith('offset');
    expect(body.context.trackedObjects.add).toHaveBeenCalledWith(target);
    expect(safeBodySearchMock).toHaveBeenCalledTimes(1);
  });

  it('falls back to normalized search when snippet text diverges', async () => {
    const { anchorByOffsets } = await import('../assets/anchors');
    const body = makeBody();
    const normalizedRange = { start: 12, end: 20 };

    let callCount = 0;
    safeBodySearchMock.mockImplementation(async (_body, needle) => {
      callCount++;
      if (needle === 'foo bar' && callCount > 2) {
        return { items: [normalizedRange] };
      }
      return { items: [] };
    });

    const onMethod = vi.fn();
    const range = await anchorByOffsets({
      body: body as any,
      snippet: 'Foo\nBar',
      start: 10,
      end: 18,
      nth: 0,
      searchOptions: { matchCase: false, matchWholeWord: false },
      normalizedCandidates: ['foo bar'],
      onMethod,
    });

    expect(range).toBe(normalizedRange);
    expect(onMethod).toHaveBeenLastCalledWith('normalized');
    expect(safeBodySearchMock.mock.calls.some(call => call[1] === 'foo bar')).toBe(true);
  });
});
