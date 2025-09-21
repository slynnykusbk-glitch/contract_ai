import { describe, it, expect, beforeAll } from 'vitest';

let normalizeSnippetForSearch: (typeof import('../../anchors'))['normalizeSnippetForSearch'];

beforeAll(async () => {
  const mod = await import('../../anchors');
  normalizeSnippetForSearch = mod.normalizeSnippetForSearch;
});

describe('normalizeSnippetForSearch equivalence', () => {
  const base = 'Alpha - "beta\'s" clause';
  const replacements: Record<string, string[]> = {
    '"': ['"', '“', '”', '„', '‟', '«', '»'],
    "'": ["'", '’', '‘', '‚', '‛'],
    '-': ['-', '—', '–', '−'],
    ' ': [' ', '\u00A0'],
    '\n': ['\n', '\r', '\r\n']
  };

  const randomReplace = (ch: string): string => {
    const options = replacements[ch];
    if (!options) return ch;
    const pick = options[Math.floor(Math.random() * options.length)];
    return pick.replace('\\n', '\n').replace('\\r', '\r');
  };

  it('property: smart quotes/dashes normalize to base string', () => {
    for (let i = 0; i < 100; i++) {
      let mutated = '';
      for (const ch of base) {
        mutated += randomReplace(ch);
      }
      mutated = mutated.replace('clause', 'clause\nline');
      const newlineVariants = ['\n', '\r', '\r\n'];
      const newline = newlineVariants[Math.floor(Math.random() * newlineVariants.length)].replace('\\n', '\n').replace('\\r', '\r');
      mutated = mutated.replace('\n', newline);
      const normalized = normalizeSnippetForSearch(mutated);
      expect(normalized).toBe('Alpha - "beta\'s" clause\nline');
    }
  });
});
