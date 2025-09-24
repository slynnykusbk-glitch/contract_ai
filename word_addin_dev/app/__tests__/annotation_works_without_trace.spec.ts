import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const anchorByOffsetsMock = vi.fn();
const findAnchorsMock = vi.fn();

vi.mock('../assets/anchors', async () => {
  const actual = await vi.importActual<typeof import('../assets/anchors')>('../assets/anchors');
  return {
    ...actual,
    anchorByOffsets: anchorByOffsetsMock,
    findAnchors: findAnchorsMock,
  };
});

describe('annotation without trace fallback', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    anchorByOffsetsMock.mockReset();
    findAnchorsMock.mockReset();
    (globalThis as any).__lastAnalyzed = 'alpha beta gamma';
    delete (globalThis as any).__traceCache;
    delete (globalThis as any).__lastCid;
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } };
    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => {
        const body = {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
        } as any;
        const ctx = {
          document: { body },
          sync: vi.fn(async () => {}),
        };
        return await cb(ctx);
      },
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (globalThis as any).__lastAnalyzed;
    delete (globalThis as any).Word;
    delete (globalThis as any).Office;
    vi.resetModules();
  });

  it('still annotates findings when no trace data is available', async () => {
    const range = {
      start: 0,
      end: 11,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}), document: { comments: { add: vi.fn() } } },
      insertComment: vi.fn(),
      parentContentControl: null,
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn(),
      }),
    } as any;
    anchorByOffsetsMock.mockResolvedValue(range);
    findAnchorsMock.mockResolvedValue([]);

    const annotateMod = await import('../assets/annotate');
    const originalSafeInsert = annotateMod.safeInsertComment;
    vi.spyOn(annotateMod, 'safeInsertComment').mockImplementation(
      async (...args: Parameters<typeof annotateMod.safeInsertComment>) => {
        return await originalSafeInsert(...args);
      }
    );
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const findings = [
      {
        rule_id: 'rule-a',
        snippet: 'alpha beta',
        start: 0,
        end: 10,
      },
    ];

    const inserted = await annotateMod.annotateFindingsIntoWord(findings as any);

    expect(inserted).toBe(1);
    expect(anchorByOffsetsMock).toHaveBeenCalled();
    expect(range.context.document.comments.add).toHaveBeenCalled();
  });
});
