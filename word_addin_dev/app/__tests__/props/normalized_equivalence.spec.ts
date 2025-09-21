import { describe, it, expect, beforeAll } from 'vitest';

let normalizeSnippetForSearch: (typeof import('../../assets/anchors'))['normalizeSnippetForSearch'];
let normalizeIntakeText: (typeof import('../../assets/normalize_intake'))['normalizeIntakeText'];
let normalizeText: (typeof import('../../assets/dedupe'))['normalizeText'];

beforeAll(async () => {
  const anchorsMod = await import('../../assets/anchors');
  normalizeSnippetForSearch = anchorsMod.normalizeSnippetForSearch;
  const intakeMod = await import('../../assets/normalize_intake');
  normalizeIntakeText = intakeMod.normalizeIntakeText;
  const dedupeMod = await import('../../assets/dedupe');
  normalizeText = dedupeMod.normalizeText;
});

describe('normalizeIntakeText', () => {
  const base = 'Alpha - "beta\'s" clause';
  const replacements: Record<string, string[]> = {
    '"': ['"', '“', '”', '„', '‟', '«', '»'],
    "'": ["'", '’', '‘', '‚', '‛'],
    '-': ['-', '—', '–', '−', '‒'],
    ' ': [' ', '\u00A0'],
    '\n': ['\n', '\r', '\r\n']
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
      const newline = newlineVariants[Math.floor(Math.random() * newlineVariants.length)].replace('\\n', '\n').replace('\\r', '\r');
      mutated = mutated.replace('\n', newline);
      const normalized = normalizeIntakeText(mutated);
      expect(normalized).toBe('Alpha - "beta\'s" clause\nline');
    }
  });

  it('handles zero-width characters, NFC and nbsp', () => {
    const cases: Array<[string, string]> = [
      ['A\u200Bgreement — “Quote”\u00A0', 'Agreement - "Quote"'],
      ['Cafe\u0301', 'Café'],
      [' Foo\t\tBar ', 'Foo Bar']
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
});

describe('normalizeSnippetForSearch', () => {
  it('delegates to intake normalization', () => {
    const sample = 'A\u200Bgreement — “Quote”\u00A0';
    expect(normalizeSnippetForSearch(sample)).toBe(normalizeIntakeText(sample));
  });
});
