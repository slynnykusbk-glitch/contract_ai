import { describe, it, expect, beforeAll } from 'vitest';

let normalizeTextFull: (typeof import('../assets/normalize_full'))['normalizeTextFull'];
let normalizeIntakeText: (typeof import('../assets/normalize_intake'))['normalizeIntakeText'];

beforeAll(async () => {
  const fullMod = await import('../assets/normalize_full');
  normalizeTextFull = fullMod.normalizeTextFull;
  const intakeMod = await import('../assets/normalize_intake');
  normalizeIntakeText = intakeMod.normalizeIntakeText;
});

describe('normalizeTextFull', () => {
  it('normalizes smart punctuation and builds offset map', () => {
    const sample = '“A”\u00A0B\u200B\r\nC\u2014D';
    const result = normalizeTextFull(sample);
    expect(result.text).toBe('"A" B\nC-D');
    expect(result.map).toEqual([0, 1, 2, 3, 4, 6, 8, 9, 10]);
    expect(result.map.length).toBe(result.text.length);
  });

  it('trims and collapses whitespace while maintaining offsets', () => {
    const sample = '\u200B  Foo\u00A0 \tBar\u200D  ';
    const result = normalizeTextFull(sample);
    expect(result.text).toBe('Foo Bar');
    expect(result.map).toEqual([3, 4, 5, 6, 9, 10, 11]);
    expect(result.map.length).toBe(result.text.length);
  });

  it('matches normalizeIntakeText output for representative samples', () => {
    const samples = [
      'Simple text',
      ' “Quote” — dash ',
      'A\u00A0B\u200B C',
      'Line1\rLine2',
      'Zero\u200DWidth',
    ];
    for (const sample of samples) {
      const result = normalizeTextFull(sample);
      expect(result.text).toBe(normalizeIntakeText(sample));
      expect(result.map.length).toBe(result.text.length);
      const sorted = [...result.map].sort((a, b) => a - b);
      expect(result.map).toEqual(sorted);
    }
  });

  it('returns empty result for falsy input', () => {
    expect(normalizeTextFull(null)).toEqual({ text: '', map: [] });
    expect(normalizeTextFull(undefined)).toEqual({ text: '', map: [] });
    expect(normalizeTextFull('')).toEqual({ text: '', map: [] });
  });
});
