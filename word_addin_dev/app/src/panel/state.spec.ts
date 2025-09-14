import { describe, it, expect, vi } from 'vitest';
import { PanelState, nextFinding, prevFinding, addCommentAtRange } from './state';

vi.mock('../assets/safeBodySearch.ts', () => ({
  safeBodySearch: vi.fn(async () => ({ items: [{ select: vi.fn(), font: {} }] }))
}));

vi.mock('../assets/api-client.ts', () => ({
  postJSON: vi.fn(async () => ({ plainText: '', ops: [] }))
}));
const safeInsertMock = vi.fn()
  .mockRejectedValueOnce(new Error('fail'))
  .mockResolvedValue(undefined);
vi.mock('../assets/annotate.ts', () => ({
  safeInsertComment: (...args: any[]) => safeInsertMock(...args)
}));

describe('navigation', () => {
  it('moves selection with next/prev', async () => {
    const state: PanelState = {
      mode: 'friendly',
      items: [
        { id: 'a', anchor: 'one' },
        { id: 'b', anchor: 'two' }
      ],
      cachedDrafts: new Map(),
      correlationId: 'cid'
    };
    const doc = { body: {} } as any;
    await nextFinding(state, doc);
    expect(state.selectedId).toBe('a');
    await nextFinding(state, doc);
    expect(state.selectedId).toBe('b');
    await prevFinding(state, doc);
    expect(state.selectedId).toBe('a');
  });
});

describe('addCommentAtRange', () => {
  it('falls back to paragraph comment on error', async () => {
    const p: any = {};
    const range: any = {
      paragraphs: { getFirst: () => p }
    };
    await addCommentAtRange(range, 'hi');
    expect(safeInsertMock).toHaveBeenNthCalledWith(1, range, 'hi');
    expect(safeInsertMock).toHaveBeenNthCalledWith(2, p, 'hi');
  });
});
