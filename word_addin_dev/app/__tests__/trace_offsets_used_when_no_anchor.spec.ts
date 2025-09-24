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

describe('trace offsets fallback', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    anchorByOffsetsMock.mockReset();
    findAnchorsMock.mockReset();
    (globalThis as any).__lastAnalyzed = 'Lorem ipsum dolor sit amet lorem ipsum';
    (globalThis as any).__traceCache = new Map();
    (globalThis as any).__lastCid = 'cid-1';
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
    delete (globalThis as any).__traceCache;
    delete (globalThis as any).__lastCid;
    delete (globalThis as any).__lastAnalyzed;
    delete (globalThis as any).Word;
    delete (globalThis as any).Office;
    vi.resetModules();
  });

  it('adds trace offsets before text variants when anchor is missing', async () => {
    const span = { start: 12, end: 22 };
    const range = {
      ...span,
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

    anchorByOffsetsMock.mockImplementation(async opts => {
      expect(opts.normalizedCandidates?.[0]).toEqual(span);
      return range;
    });
    findAnchorsMock.mockResolvedValue([]);

    const traceBody = {
      dispatch: {
        segments: [
          {
            segment_id: 7,
            candidates: [
              {
                rule_id: 'rule-1',
                reasons: [
                  { offsets: [{ start: 12, end: 22 }, { start: 12, end: 22 }, { start: 30, end: 40 }] },
                ],
              },
            ],
          },
        ],
      },
    };
    (globalThis as any).__traceCache.set('cid-1', traceBody);

    const annotateMod = await import('../assets/annotate');
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const findings = [
      {
        rule_id: 'rule-1',
        snippet: 'ipsum dolor',
        start: 0,
        end: 11,
        segment_id: 7,
        anchor: {},
      },
    ];

    const inserted = await annotateMod.annotateFindingsIntoWord(findings as any);

    expect(inserted).toBe(1);
    expect(anchorByOffsetsMock).toHaveBeenCalledTimes(1);
    expect(findAnchorsMock).not.toHaveBeenCalled();
  });
});
