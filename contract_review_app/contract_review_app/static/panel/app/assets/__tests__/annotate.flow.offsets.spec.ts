import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const searchNthMock = vi.fn();
const findAnchorsMock = vi.fn();
let annotateMod: Awaited<typeof import('../annotate.ts')>;
let annotateFindingsIntoWord: (typeof import('../annotate.ts'))['annotateFindingsIntoWord'];

vi.mock('../anchors.ts', async () => {
  const actual = await vi.importActual<typeof import('../anchors.ts')>('../anchors.ts');
  return {
    ...actual,
    searchNth: searchNthMock,
    findAnchors: findAnchorsMock
  };
});

describe('annotate flow offsets', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    searchNthMock.mockReset();
    findAnchorsMock.mockReset();
    (globalThis as any).document = { getElementById: () => null };
    annotateMod = await import('../annotate.ts');
    annotateFindingsIntoWord = annotateMod.annotateFindingsIntoWord;
  });

  afterEach(() => {
    delete (globalThis as any).Word;
    delete (globalThis as any).__lastAnalyzed;
    delete (globalThis as any).document;
    vi.restoreAllMocks();
  });

  it('anchors to the expected occurrence from offsets', async () => {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const textPath = path.resolve(here, './fixtures/texts/para_multi_occurrence.txt');
    const payloadPath = path.resolve(here, './fixtures/payloads/finding_offsets.json');
    const baseText = fs.readFileSync(textPath, 'utf8');
    const finding = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));

    (globalThis as any).__lastAnalyzed = baseText;

    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const targetRange = {
      start: finding.start,
      end: finding.end,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn()
      })
    } as any;

    searchNthMock.mockImplementation(async (_body, needle, nth) => {
      expect(needle).toBe(finding.snippet);
      expect(nth).toBe(finding.nth);
      return targetRange;
    });

    findAnchorsMock.mockResolvedValue([]);

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => ({
            context: { sync: vi.fn(async () => {}) },
            insertContentControl: () => ({
              tag: '',
              title: '',
              color: '',
              insertText: vi.fn()
            })
          }))
        }
      },
      sync: vi.fn(async () => {})
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx)
    };

    const inserted = await annotateFindingsIntoWord([finding] as any);
    expect(inserted).toBe(1);
    expect(targetRange.load).toHaveBeenCalledWith(['start', 'end']);
  });

  it('uses the reordered nth anchor when offset anchoring fails', async () => {
    const baseText = 'foo bar foo bar foo bar foo bar';
    (globalThis as any).__lastAnalyzed = baseText;
    const snippet = 'foo bar';

    const starts: number[] = [];
    let idx = -1;
    while ((idx = baseText.indexOf(snippet, idx + 1)) !== -1) {
      starts.push(idx);
    }

    const insertedStarts: number[] = [];

    const makeRange = (start: number) => ({
      start,
      end: start + snippet.length,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertContentControl: () => {
        insertedStarts.push(start);
        return {
          tag: '',
          title: '',
          color: '',
          insertText: vi.fn()
        };
      }
    });

    const preferredRange = makeRange(starts[2]);

    const otherRanges = [starts[0], starts[1]].map(makeRange) as any[];

    searchNthMock.mockResolvedValue(null);
    findAnchorsMock.mockImplementation(async (_body, text, opts) => {
      expect(text).toBe(snippet);
      expect(opts?.nth).toBe(2);
      return [preferredRange, ...otherRanges];
    });

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => ({
            context: { sync: vi.fn(async () => {}) },
            insertContentControl: () => ({
              tag: '',
              title: '',
              color: '',
              insertText: vi.fn()
            })
          }))
        }
      },
      sync: vi.fn(async () => {})
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx)
    };

    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };

    const finding = { rule_id: 'r2', snippet, start: preferredRange.start, end: preferredRange.end, nth: 2 };

    const inserted = await annotateFindingsIntoWord([finding] as any);
    expect(inserted).toBe(1);
    expect(insertedStarts).toEqual([preferredRange.start]);
    expect(preferredRange.load).toHaveBeenCalledWith(['start', 'end']);
    expect(findAnchorsMock).toHaveBeenCalledWith(expect.anything(), snippet, { nth: 2 });
  });
});
