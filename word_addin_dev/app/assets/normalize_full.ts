const ZERO_WIDTH_CHARS = new Set<string>([
  '\u200B',
  '\u200C',
  '\u200D',
  '\u200E',
  '\u200F',
  '\u2060',
  '\u2061',
  '\u2062',
  '\u2063',
  '\u2064',
  '\uFEFF',
]);

const NBSP_CHARS = new Set<string>(['\u00A0', '\u202F']);

const dashMap: Record<string, string> = {
  '\u2010': '-',
  '\u2011': '-',
  '\u2012': '-',
  '\u2013': '-',
  '\u2014': '-',
  '\u2015': '-',
  '\u2212': '-',
};

const doubleQuoteMap: Record<string, string> = {
  '\u201C': '"',
  '\u201D': '"',
  '\u201E': '"',
  '\u201F': '"',
  '\u00AB': '"',
  '\u00BB': '"',
  '\u2033': '"',
  '\u2036': '"',
};

const singleQuoteMap: Record<string, string> = {
  '\u2018': "'",
  '\u2019': "'",
  '\u201A': "'",
  '\u201B': "'",
  '\u2032': "'",
  '\u2035': "'",
};

export interface NormalizeTextFullResult {
  text: string;
  map: number[];
}

function isZeroWidthChar(ch: string): boolean {
  return ZERO_WIDTH_CHARS.has(ch);
}

function replaceSmartChar(ch: string): string {
  if (dashMap[ch]) return dashMap[ch];
  if (doubleQuoteMap[ch]) return doubleQuoteMap[ch];
  if (singleQuoteMap[ch]) return singleQuoteMap[ch];
  if (NBSP_CHARS.has(ch)) return ' ';
  return ch;
}

function trimNormalized(result: NormalizeTextFullResult): NormalizeTextFullResult {
  const { text, map } = result;
  let start = 0;
  let end = text.length;
  while (start < end && /\s/.test(text[start]!)) start++;
  while (end > start && /\s/.test(text[end - 1]!)) end--;
  if (start === 0 && end === text.length) {
    return result;
  }
  return {
    text: text.slice(start, end),
    map: map.slice(start, end),
  };
}

export function normalizeTextFull(input: string | null | undefined): NormalizeTextFullResult {
  const source = typeof input === 'string' ? input.normalize('NFC') : '';
  if (!source) {
    return { text: '', map: [] };
  }

  const chars: string[] = [];
  const map: number[] = [];
  let prevSpace = false;

  for (let i = 0; i < source.length; ) {
    const codePoint = source.codePointAt(i)!;
    let ch = String.fromCodePoint(codePoint);
    const step = ch.length;

    if (ch === '\r') {
      map.push(i);
      chars.push('\n');
      i += step;
      if (i < source.length && source[i] === '\n') {
        i += 1;
      }
      prevSpace = false;
      continue;
    }

    if (ch === '\n') {
      map.push(i);
      chars.push('\n');
      i += step;
      prevSpace = false;
      continue;
    }

    if (isZeroWidthChar(ch)) {
      i += step;
      continue;
    }

    ch = replaceSmartChar(ch);
    if (ch === '\t') ch = ' ';

    if (ch === ' ') {
      if (prevSpace) {
        i += step;
        continue;
      }
      prevSpace = true;
    } else {
      prevSpace = false;
    }

    chars.push(ch);
    map.push(i);
    i += step;
  }

  const normalized = chars.join('').normalize('NFC');
  const result: NormalizeTextFullResult = { text: normalized, map };
  return trimNormalized(result);
}

