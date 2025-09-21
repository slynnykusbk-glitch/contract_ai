import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const safeBodySearchMock = vi.fn();
const searchNthMock = vi.fn();
const findAnchorsMock = vi.fn();
let annotateMod: Awaited<typeof import('../annotate.ts')>;
let annotateFindingsIntoWord: (typeof import('../annotate.ts'))['annotateFindingsIntoWord'];

vi.mock('../safeBodySearch.ts', () => ({
  safeBodySearch: safeBodySearchMock,
}));

vi.mock('../anchors.ts', async () => {
  const actual = await vi.importActual<typeof import('../anchors.ts')>('../anchors.ts');
  return {
    ...actual,
    searchNth: searchNthMock,
    findAnchors: findAnchorsMock,
  };
});

describe('annotate anchor by offsets', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    safeBodySearchMock.mockReset();
    searchNthMock.mockReset();
    findAnchorsMock.mockReset();
    (globalThis as any).__lastAnalyzed = '';
    (globalThis as any).document = { getElementById: () => null };
    annotateMod = await import('../annotate.ts');
    annotateFindingsIntoWord = annotateMod.annotateFindingsIntoWord;
  });

  afterEach(() => {
    delete (globalThis as any).Word;
    delete (globalThis as any).__lastAnalyzed;
    delete (globalThis as any).__cfg_anchorOffsets;
    delete (globalThis as any).document;
    vi.restoreAllMocks();
  });

  it('anchors directly by offsets before searching nth', async () => {
    (globalThis as any).__cfg_anchorOffsets = 1;
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const snippet = 'Term 45 / Pay 60';
    const range = {
      start: 42,
      end: 42 + snippet.length,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: vi.fn(() => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn(),
      })),
    } as any;

    safeBodySearchMock.mockImplementation(async () => ({ items: [range] }));
    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = snippet;

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => range),
        },
      },
      sync: vi.fn(async () => {}),
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx),
    };

    const findings = [
      { rule_id: 'r1', snippet, start: 42, end: 42 + snippet.length },
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(safeBodySearchMock).toHaveBeenCalled();
  });

  it('falls back to nth search when offset lookup misses', async () => {
    (globalThis as any).__cfg_anchorOffsets = 1;
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const snippet = 'Clause Value';
    const range = {
      start: 10,
      end: 22,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: vi.fn(() => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn(),
      })),
    } as any;

    const queue = [
      { items: [] },
      { items: [] },
      { items: [range] },
    ];
    safeBodySearchMock.mockImplementation(async () => queue.shift() ?? { items: [] });
    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = snippet;

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => range),
        },
      },
      sync: vi.fn(async () => {}),
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx),
    };

    const findings = [
      { rule_id: 'r2', snippet, start: 10, end: 22, nth: 0 },
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
  });

  it('falls back to token search when nth searches fail', async () => {
    (globalThis as any).__cfg_anchorOffsets = 1;
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const token = 'Supercalifragilistic';
    const snippet = `Quote — “${token}”`;
    const tokenRange = {
      start: 70,
      end: 70 + token.length,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: vi.fn(() => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn(),
      })),
    } as any;

    const queue = [
      { items: [] },
      { items: [] },
      { items: [] },
      { items: [] },
      { items: [tokenRange] },
    ];
    safeBodySearchMock.mockImplementation(async () => queue.shift() ?? { items: [] });
    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = snippet;

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => tokenRange),
        },
      },
      sync: vi.fn(async () => {}),
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx),
    };

    const findings = [
      { rule_id: 'r3', snippet, start: 70, end: 70 + snippet.length },
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
  });

  it('falls back to content control when no anchor is found', async () => {
    (globalThis as any).__cfg_anchorOffsets = 1;
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: false } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: true });

    const snippet = 'Missing anchor snippet';

    safeBodySearchMock.mockImplementation(async () => ({ items: [] }));
    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = snippet;

    const ccRange = {
      context: { sync: vi.fn(async () => {}) },
      insertContentControl: vi.fn(() => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn(),
      })),
    } as any;

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => ccRange),
        },
      },
      sync: vi.fn(async () => {}),
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx),
    };

    const findings = [
      { rule_id: 'r4', snippet, start: 0, end: snippet.length },
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(ccRange.insertContentControl).toHaveBeenCalled();
  });
});
