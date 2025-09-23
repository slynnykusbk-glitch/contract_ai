import { describe, it, expect } from 'vitest';
import { COMMENT_PREFIX } from '../assets/annotate';

describe('clearAnnotations', () => {
  it('removes only prefixed comments', async () => {
    const deleted: string[] = [];
    (globalThis as any).window = globalThis;
    (globalThis as any).document = { readyState: 'complete', addEventListener: () => {} } as any;
    (globalThis as any).__CAI_TESTING__ = true;
    const mod = await import('../assets/taskpane');
    (globalThis as any).Word = {
      run: async (cb: any) => {
        const cmts = {
          items: [
            { text: `${COMMENT_PREFIX} one`, delete: () => deleted.push('a') },
            { text: 'foreign', delete: () => deleted.push('b') },
          ],
          load: () => {},
        };
        const ctx = {
          document: { comments: cmts, body: { font: { highlightColor: 'Yellow' } } },
          sync: async () => {},
        };
        await cb(ctx);
      },
    };
    await mod.clearAnnotations();
    expect(deleted).toEqual(['a']);
  });
});
