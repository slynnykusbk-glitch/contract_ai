import { describe, it, expect, beforeAll } from 'vitest';

let normalizeSnippetForSearch: (typeof import('../../assets/anchors'))['normalizeSnippetForSearch'];
let normalizeIntakeText: (typeof import('../../assets/normalize_intake'))['normalizeIntakeText'];
let normalizeTextFull: (typeof import('../../assets/normalize_full'))['normalizeTextFull'];
let normalizeText: (typeof import('../../assets/dedupe'))['normalizeText'];

beforeAll(async () => {
  const anchorsMod = await import('../../assets/anchors');
  normalizeSnippetForSearch = anchorsMod.normalizeSnippetForSearch;
  const intakeMod = await import('../../assets/normalize_intake');
  normalizeIntakeText = intakeMod.normalizeIntakeText;
  const fullMod = await import('../../assets/normalize_full');
  normalizeTextFull = fullMod.normalizeTextFull;
  const dedupeMod = await import('../../assets/dedupe');
  normalizeText = dedupeMod.normalizeText;
});

describe('normalizeIntakeText', () => {
  const CASES: Array<{ name: string; input: string; expected: string }> = [
    {
      name: 'NFC input remains stable',
      input: 'Alpha - "beta\'s" clause\nline',
      expected: 'Alpha - "beta\'s" clause\nline',
    },
    {
      name: 'NFD combines and smart punctuation',
      input: 'Cafe\u0301 — “Quote”',
      expected: 'Café - "Quote"',
    },
    {
      name: 'zero-width characters removed',
      input: 'A\u200Bgreement\u200C',
      expected: 'Agreement',
    },
    {
      name: 'collapses whitespace and nbsp',
      input: '\u00A0Foo\t\tBar\u202F',
      expected: 'Foo Bar',
    },
    {
      name: 'normalizes carriage returns',
      input: 'Line1\r\nLine2',
      expected: 'Line1\nLine2',
    },
  ];

  it('normalizes representative variants to canonical form', () => {
    for (const sample of CASES) {
      expect(normalizeIntakeText(sample.input)).toBe(sample.expected);
    }
  });

  const base = 'Alpha - "beta\'s" clause';
  const replacements: Record<string, string[]> = {
    '"': ['"', '“', '”', '„', '‟', '«', '»'],
    "'": ["'", '’', '‘', '‚', '‛'],
    '-': ['-', '—', '–', '−', '‒'],
    ' ': [' ', '\u00A0'],
    '\n': ['\n', '\r', '\r\n'],
  };

  const randomReplace = (ch: string): string => {
    const options = replacements[ch];
    if (!options) return ch;
    const pick = options[Math.floor(Math.random() * options.length)];
    return pick.replace('\\n', '\n').replace('\\r', '\r');
  };

  it('normalizes smart punctuation variants to base string', () => {
    for (let i = 0; i < 100; i++) {
      let mutated = '';
      for (const ch of base) {
        mutated += randomReplace(ch);
      }
      mutated = mutated.replace('clause', 'clause\nline');
      const newlineVariants = ['\n', '\r', '\r\n'];
      const newline = newlineVariants[Math.floor(Math.random() * newlineVariants.length)]
        .replace('\\n', '\n')
        .replace('\\r', '\r');
      mutated = mutated.replace('\n', newline);
      const normalized = normalizeIntakeText(mutated);
      expect(normalized).toBe('Alpha - "beta\'s" clause\nline');
    }
  });

  it('handles zero-width characters, NFC and nbsp', () => {
    const cases: Array<[string, string]> = [
      ['A\u200Bgreement — “Quote”\u00A0', 'Agreement - "Quote"'],
      ['Cafe\u0301', 'Café'],
      [' Foo\t\tBar ', 'Foo Bar'],
    ];
    for (const [input, expected] of cases) {
      expect(normalizeIntakeText(input)).toBe(expected);
    }
  });

  it('is idempotent', () => {
    const sample = 'A\u200Cgreement “Quote”';
    const once = normalizeIntakeText(sample);
    expect(normalizeIntakeText(once)).toBe(once);
  });

  it('matches normalization after legacy normalizeText', () => {
    const sample = ' Clause\u00A0“Alpha” ';
    expect(normalizeIntakeText(sample)).toBe(normalizeIntakeText(normalizeText(sample)));
  });

  it('produces the same output via full normalization helper', () => {
    for (const sample of CASES) {
      expect(normalizeIntakeText(sample.input)).toBe(normalizeTextFull(sample.input).text);
    }
  });
});

describe('normalizeSnippetForSearch', () => {
  it('delegates to intake normalization', () => {
    const sample = 'A\u200Bgreement — “Quote”\u00A0';
    expect(normalizeSnippetForSearch(sample)).toBe(normalizeIntakeText(sample));
  });
});

describe('normalizeTextFull', () => {
  it('returns offset map aligned with normalized text', () => {
    const sample = ' Cafe\u0301\u200B — “Q”\r\nLine\u00A0';
    const result = normalizeTextFull(sample);
    expect(result.text).toBe('Café - "Q"\nLine');
    expect(result.map).toEqual([1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17]);
    expect(result.map).toHaveLength(result.text.length);
  });

  it('keeps map length in sync for representative samples', () => {
    const samples = ['Cafe\u0301', 'A\u200B', ' Foo\tBar ', 'Line1\r\nLine2'];
    for (const sample of samples) {
      const result = normalizeTextFull(sample);
      expect(result.map).toHaveLength(result.text.length);
    }
  });
});
