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
});
